"""Review rules for Postman environment / globals files. Findings use endpoint_id=None and group="Environment".

Raw values are never put into a finding: evidence always carries the masked form (e.g. "eyJh****").
"""
from __future__ import annotations

import base64
import json
import math
import re
from urllib.parse import urlsplit

from ..models import Environment, EnvVar, Finding
from ..parsers.common import is_placeholder, looks_like_secret_value, mask, mask_url_secrets

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
SECRET_WORDS = {"password", "passwd", "pwd", "pass", "token", "secret", "apikey", "key", "signature",
                "credential", "credentials", "passphrase"}
PRIVILEGED_WORDS = {"admin", "root", "master", "superuser", "sudo"}
PRIVILEGED_ROLES = {"service_role", "admin", "root", "superuser", "supabase_admin", "postgres"}
_UUID_RE = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
_RANDOM_RE = re.compile(r"^[A-Za-z0-9_\-+/=.]{24,}$")


def words(name: str) -> list[str]:
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return [w.lower() for w in re.split(r"[^A-Za-z0-9]+", spaced) if w]


def has_secret_name(name: str) -> bool:
    ws = words(name)
    return bool(SECRET_WORDS & set(ws)) or "apikey" in name.lower().replace("_", "").replace("-", "")


def _jwt_role(value: str) -> str | None:
    parts = value.split(".")
    if len(parts) != 3 or not value.startswith("eyJ"):
        return None
    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
        role = claims.get("role") if isinstance(claims, dict) else None
        return str(role) if role else None
    except Exception:  # not a decodable JWT
        return None


def _entropy(s: str) -> float:
    return -sum((s.count(c) / len(s)) * math.log2(s.count(c) / len(s)) for c in set(s))


def real_looking_secret(name: str, value: str) -> bool:
    if looks_like_secret_value(value):
        return True
    if not _RANDOM_RE.match(value) or _UUID_RE.match(value):
        return False
    classes = sum([bool(re.search(r"[a-z]", value)), bool(re.search(r"[A-Z]", value)), bool(re.search(r"\d", value))])
    return _entropy(value) >= 3.5 and (classes == 3 or (classes >= 2 and has_secret_name(name)))


def _safe_url(value: str) -> str:
    return mask_url_secrets(re.sub(r"^(https?://)[^/@\s]*@", r"\g<1>****@", value, flags=re.I))


def _privileged(v: EnvVar) -> str | None:
    """Reason string when the variable looks like a service-role / admin / root credential."""
    ws = set(words(v.key))
    if {"service", "role"} <= ws:
        return "name suggests a service-role key"
    if ws & PRIVILEGED_WORDS and ws & (SECRET_WORDS | {"key"}):
        return "name suggests an admin/root credential"
    role = _jwt_role(v.value)
    if role and role.lower() in PRIVILEGED_ROLES:
        return f"token carries privileged role claim '{role}'"
    return None


def _finding(issue: str, evidence: str, severity: str, refs: list[str], remediation: str) -> Finding:
    return Finding(id="", endpoint_id=None, group="Environment", issue=issue, evidence_masked=evidence,
                   severity=severity, standard_refs=refs, remediation=remediation)  # type: ignore[arg-type]


def review_environment(env: Environment) -> list[Finding]:
    out: list[Finding] = []
    for v in env.variables:
        if not v.enabled or is_placeholder(v.value):
            continue  # placeholders such as "<lawyer password>" and empty values are never findings
        val = v.value.strip()

        if re.match(r"^http://", val, re.I):
            host = (urlsplit(val).hostname or "").lower()
            local = host in LOCAL_HOSTS
            out.append(_finding(
                f"Environment variable '{v.key}' uses a plain-HTTP URL" + (" (local development host)" if local else ""),
                f"{v.key} = {_safe_url(val)}", "Low" if local else "Medium",
                ["API8:2023", "CWE-319", "ASVS V9.1.1"],
                "Use https:// for every non-local base URL so credentials and data are encrypted in transit."))

        privileged = _privileged(v)
        if privileged:
            out.append(_finding(
                f"Privileged (service-role/admin/root) credential in a shared environment: '{v.key}'",
                f"variable '{v.key}' (type: {v.type}) = {mask(val)}; {privileged}", "High",
                ["API8:2023", "CWE-798", "ASVS V2.10.4", "ASVS V4.1.3"],
                "Remove privileged keys from shared environments, rotate the exposed key and keep it in a server-side secret store."))
            continue

        if v.type == "default" and has_secret_name(v.key) and not val.lower().startswith(("http://", "https://")):
            out.append(_finding(
                f"Secret-like variable '{v.key}' stored as type 'default' instead of 'secret'",
                f"variable '{v.key}' (type: default) = {mask(val)}", "Medium",
                ["API8:2023", "CWE-522", "ASVS V2.10.4"],
                "Set the variable type to 'secret' (masks it in the Postman UI) and keep the value out of exported/shared files."))

        if real_looking_secret(v.key, val):
            out.append(_finding(
                f"Real-looking secret value stored in variable '{v.key}'",
                f"variable '{v.key}' (type: {v.type}) = {mask(val)}", "High",
                ["API8:2023", "CWE-798", "ASVS V2.10.4"],
                "Do not commit or share real credentials in environment exports; use placeholders and rotate any exposed value."))
    for i, f in enumerate(out, 1):
        f.id = f"E-{i:03d}"
    return out
