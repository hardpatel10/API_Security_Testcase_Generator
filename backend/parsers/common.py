"""Helpers shared by the Postman and OpenAPI parsers."""
from __future__ import annotations

import re
from typing import Any

from ..models import SecretRef


class ParseError(ValueError):
    """Raised for invalid / unsupported input files. message/hint are user-facing; code is machine-readable."""

    def __init__(self, message: str, code: str = "INVALID_FORMAT", hint: str = "",
                 line: int | None = None, column: int | None = None):
        super().__init__(message)
        self.message, self.code, self.hint, self.line, self.column = message, code, hint, line, column


SECRET_NAME_RE = re.compile(
    r"(pass(word|wd)?|secret|token|api[-_]?key|apikey|authorization|bearer|private[-_]?key|"
    r"client[-_]?secret|access[-_]?key|credential|x-api-key)",
    re.I,
)

SECRET_VALUE_RES = [
    re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\.[A-Za-z0-9_-]*"),  # JWT
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),  # AWS access key id
    re.compile(r"\b(sk|pk|rk)_(live|test)_[A-Za-z0-9]{8,}\b"),  # Stripe style
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),  # GitHub tokens
]

PLACEHOLDER_VALUES = {
    "", "string", "example", "your_token", "your-token", "token", "xxx", "xxxx", "changeme",
    "<token>", "null", "none", "undefined", "true", "false",
}

VAR_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


def mask(value: Any) -> str:
    """Mask a secret value: keep at most the first 4 chars, e.g. 'eyJh****'."""
    s = str(value)
    # keep auth scheme visible: "Bearer eyJhbGci..." -> "Bearer eyJh****"
    m = re.match(r"^(Bearer|Basic|Token)\s+(.+)$", s, re.I)
    if m:
        return f"{m.group(1)} {mask(m.group(2))}"
    if len(s) <= 4:
        return "****"
    return s[:4] + "****"


def is_placeholder(value: Any) -> bool:
    """True when a value is empty, a template variable, or an obvious placeholder."""
    if value is None:
        return True
    s = str(value).strip()
    if s.lower() in PLACEHOLDER_VALUES:
        return True
    if "{{" in s or "${" in s:
        return True
    if re.fullmatch(r"<[^>]*>", s) or re.fullmatch(r"\{[^{}]*\}", s):
        return True
    m = re.match(r"^(Bearer|Basic|Token)\s+(.*)$", s, re.I)
    if m:
        return is_placeholder(m.group(2)) if m.group(2) else True
    return False


def looks_like_secret_value(value: Any) -> bool:
    s = str(value)
    return any(r.search(s) for r in SECRET_VALUE_RES)


def find_secret(location: str, name: str, value: Any) -> SecretRef | None:
    """Return a SecretRef if (name, value) looks like a hard-coded credential."""
    if value is None or isinstance(value, (dict, list, bool)):
        return None
    if is_placeholder(value):
        return None
    if SECRET_NAME_RE.search(name or "") or looks_like_secret_value(value):
        return SecretRef(location=location, name=name, masked=mask(value))
    return None


def mask_if_secret(name: str, value: str) -> str:
    """Masked copy of a header/query value for safe echo in API output."""
    if value and not is_placeholder(value) and (SECRET_NAME_RE.search(name) or looks_like_secret_value(value)):
        return mask(value)
    return value


def resolve_vars(text: str, variables: dict[str, str]) -> str:
    """Substitute {{var}} where a non-empty value is known (up to 3 nested passes)."""
    if not text or "{{" not in text:
        return text

    def sub(m: re.Match) -> str:
        v = variables.get(m.group(1))
        return v if v else m.group(0)

    for _ in range(3):
        new = VAR_RE.sub(sub, text)
        if new == text:
            break
        text = new
    return text


_PATH_PARAM_RES = [
    re.compile(r"/:([A-Za-z_]\w*)"),
    re.compile(r"(?<!\{)\{([^{}/]+)\}(?!\})"),
]


def extract_path_params(path: str) -> list[str]:
    out: list[str] = []
    for r in _PATH_PARAM_RES:
        for m in r.finditer(path):
            if m.group(1) not in out:
                out.append(m.group(1))
    return out


def path_of(url: str) -> str:
    """The path portion of a URL (drops scheme/host/{{baseUrl}} prefix and query string)."""
    u = url.split("?", 1)[0].split("#", 1)[0]
    u = re.sub(r"^[A-Za-z][A-Za-z0-9+.-]*://[^/]*", "", u)
    u = re.sub(r"^\{\{[^{}]+\}\}", "", u)
    return u


def flatten_keys(obj: Any, prefix: str = "", depth: int = 0, out: list | None = None,
                 leaves: list | None = None) -> list[str]:
    """Flatten a JSON-like object to dotted key names. Optionally collects (name, value) leaves."""
    if out is None:
        out = []
    if depth > 4:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            name = f"{prefix}.{k}" if prefix else str(k)
            out.append(name)
            if isinstance(v, (dict, list)):
                flatten_keys(v, name, depth + 1, out, leaves)
            elif leaves is not None:
                leaves.append((str(k), v))
    elif isinstance(obj, list) and obj:
        flatten_keys(obj[0], f"{prefix}[]" if prefix else "[]", depth + 1, out, leaves)
    return out


def dedupe(seq: list[str]) -> list[str]:
    seen: set[str] = set()
    out = []
    for s in seq:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def classify_header_auth(headers: dict[str, str]) -> str | None:
    """Infer auth type from a raw header set; None when no auth header is present."""
    for k, v in headers.items():
        kl = k.lower()
        if kl == "authorization":
            vl = (v or "").strip().lower()
            if vl.startswith("basic"):
                return "basic"
            if vl.startswith("bearer") or vl.startswith("{{"):
                return "bearer"
            return "other"
        if kl in ("x-api-key", "api-key", "apikey", "x-auth-token", "x-access-token"):
            return "apikey-header"
    return None


QUERY_KEY_NAMES = {"api_key", "apikey", "api-key", "key", "access_token", "token", "auth_token"}


def classify_query_auth(query_params: list[str]) -> str | None:
    for q in query_params:
        if q.lower() in QUERY_KEY_NAMES:
            return "apikey-query"
    return None


def mask_url_secrets(url: str) -> str:
    """Mask secret-looking query values inside a URL so they are never echoed back."""
    if "?" not in url:
        return url
    base, _, rest = url.partition("?")
    query, hash_sep, frag = rest.partition("#")
    parts = []
    for pair in query.split("&"):
        k, eq, v = pair.partition("=")
        if eq and find_secret("query", k, v):
            v = mask(v)
        parts.append(k + eq + v)
    return base + "?" + "&".join(parts) + (hash_sep + frag if hash_sep else "")


_TEMPLATE_PLACEHOLDER_RE = re.compile(r"<[^>]*>")


def resolution_value(name: str, value: Any) -> str | None:
    """Value to substitute for {{name}}, or None to leave the variable unresolved.

    Placeholders ("<lawyer password>", "", "string"...) are never substituted. Secret-looking values are
    substituted in masked form so real secrets can never leak into URLs/headers echoed by the API.
    """
    if value is None:
        return None
    s = str(value)
    if s.strip().lower() in PLACEHOLDER_VALUES or _TEMPLATE_PLACEHOLDER_RE.fullmatch(s.strip()):
        return None
    if re.match(r"^https?://", s, re.I):
        return mask_url_secrets(re.sub(r"^(https?://)[^/@\s]*@", r"\g<1>****@", s, flags=re.I))
    if SECRET_NAME_RE.search(name or "") or looks_like_secret_value(s):
        return mask(s)
    return s
