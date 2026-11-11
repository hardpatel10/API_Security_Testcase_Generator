"""Postman Collection v2.0 / v2.1 parser."""
from __future__ import annotations

import json
import re
from typing import Any

from ..models import Collection, Endpoint, SecretRef
from .common import (
    VAR_RE, ParseError, classify_header_auth, classify_query_auth, dedupe, extract_path_params,
    find_secret, flatten_keys, is_placeholder, mask, mask_if_secret, mask_url_secrets, path_of, resolution_value,
    resolve_vars,
)

HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE"}


def _kv_list_to_dict(lst: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    if isinstance(lst, list):
        for e in lst:
            if isinstance(e, dict) and e.get("key") is not None:
                out[str(e["key"])] = "" if e.get("value") is None else str(e.get("value"))
    return out


def _auth_params(auth: dict) -> dict[str, str]:
    return _kv_list_to_dict(auth.get(auth.get("type", ""), []))


def _auth_type_and_secrets(auth: dict) -> tuple[str, list[SecretRef]]:
    t = str(auth.get("type", "")).lower()
    params = _auth_params(auth)
    secrets: list[SecretRef] = []
    if t == "noauth":
        return "none", secrets
    if t == "bearer":
        s = find_secret("auth", "bearer token", params.get("token"))
        if s is None and params.get("token") and not is_placeholder(params["token"]):
            s = SecretRef(location="auth", name="bearer token", masked=mask(params["token"]))
        if s:
            secrets.append(s)
        return "bearer", secrets
    if t == "basic":
        pw = params.get("password")
        if pw and not is_placeholder(pw):
            secrets.append(SecretRef(location="auth", name="basic password", masked=mask(pw)))
        return "basic", secrets
    if t == "apikey":
        v = params.get("value")
        if v and not is_placeholder(v):
            secrets.append(SecretRef(location="auth", name=params.get("key", "api key"), masked=mask(v)))
        return ("apikey-query" if params.get("in") == "query" else "apikey-header"), secrets
    if t in ("oauth2", "oauth1"):
        tok = params.get("accessToken")
        if tok and not is_placeholder(tok):
            secrets.append(SecretRef(location="auth", name="access token", masked=mask(tok)))
        return "oauth2" if t == "oauth2" else "other", secrets
    return "other", secrets


def _parse_json_body(raw: str) -> Any | None:
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        pass
    try:  # templated bodies: replace {{var}} with a dummy literal and retry
        return json.loads(VAR_RE.sub("0", raw))
    except (ValueError, TypeError):
        return None


class _Walker:
    def __init__(self, variables: dict[str, str]):
        self.variables = variables
        self.endpoints: list[Endpoint] = []
        self.warnings: list[str] = []

    def walk(self, items: list, folder: list[str], inherited_auth: dict | None) -> None:
        for it in items:
            if not isinstance(it, dict):
                continue
            auth = it.get("auth") if isinstance(it.get("auth"), dict) else inherited_auth
            if isinstance(it.get("item"), list):
                self.walk(it["item"], folder + [str(it.get("name", ""))], auth)
            elif isinstance(it.get("request"), (dict, str)):
                self._request(it, folder, auth)

    def _request(self, item: dict, folder: list[str], auth: dict | None) -> None:
        req = item["request"]
        if isinstance(req, str):  # legacy: request is just a URL string
            req = {"method": "GET", "url": req}
        method = str(req.get("method", "GET")).upper()
        if method not in HTTP_METHODS:
            self.warnings.append(f"Skipped '{item.get('name')}': unsupported method {method}")
            return

        # ---- URL, query and path params
        u = req.get("url", "")
        query_params: list[str] = []
        explicit_path_vars: list[str] = []
        query_values: list[tuple[str, str]] = []
        if isinstance(u, dict):
            raw = u.get("raw")
            if not raw:
                host = ".".join(u["host"]) if isinstance(u.get("host"), list) else str(u.get("host", ""))
                path = "/".join(u["path"]) if isinstance(u.get("path"), list) else str(u.get("path", ""))
                proto = u.get("protocol")
                raw = (f"{proto}://" if proto else "") + host + ("/" + path if path else "")
            for q in u.get("query", []) or []:
                if isinstance(q, dict) and q.get("key") and not q.get("disabled"):
                    query_params.append(str(q["key"]))
                    query_values.append((str(q["key"]), "" if q.get("value") is None else str(q["value"])))
            for v in u.get("variable", []) or []:
                if isinstance(v, dict) and v.get("key"):
                    explicit_path_vars.append(str(v["key"]))
        else:
            raw = str(u or "")
        if not query_params and "?" in raw:
            for pair in raw.split("?", 1)[1].split("#")[0].split("&"):
                if pair:
                    k, _, v = pair.partition("=")
                    query_params.append(k)
                    query_values.append((k, v))
        raw_clean = raw.split("?", 1)[0] if "?" in raw and not isinstance(u, dict) else raw
        url_resolved = resolve_vars(raw, self.variables)
        path_params = dedupe(explicit_path_vars + extract_path_params(path_of(url_resolved)))

        # ---- headers
        raw_headers: dict[str, str] = {}
        for h in req.get("header", []) or []:
            if isinstance(h, dict) and h.get("key") and not h.get("disabled"):
                raw_headers[str(h["key"])] = "" if h.get("value") is None else str(h["value"])

        secrets: list[SecretRef] = []
        for k, v in raw_headers.items():
            s = find_secret("header", k, v)
            if s:
                secrets.append(s)
        for k, v in query_values:
            s = find_secret("query", k, v)
            if s:
                secrets.append(s)

        # ---- body
        body_fields: list[str] = []
        has_upload = False
        content_type = next((v for k, v in raw_headers.items() if k.lower() == "content-type"), None)
        body = req.get("body") if isinstance(req.get("body"), dict) else None
        if body:
            mode = body.get("mode")
            if mode == "raw":
                text = body.get("raw") or ""
                lang = (((body.get("options") or {}).get("raw") or {}).get("language")) or ""
                parsed = _parse_json_body(text) if text.strip() else None
                if parsed is not None:
                    leaves: list = []
                    body_fields = flatten_keys(parsed, leaves=leaves)  # secrets are judged on the unresolved text
                    resolved_text = resolve_vars(text, self.variables)
                    if resolved_text != text:
                        resolved = _parse_json_body(resolved_text)
                        if resolved is not None:
                            body_fields = flatten_keys(resolved)
                    content_type = content_type or "application/json"
                    for name, val in leaves:
                        s = find_secret("body", name, val)
                        if s:
                            secrets.append(s)
                else:
                    if lang == "xml":
                        content_type = content_type or "application/xml"
            elif mode in ("urlencoded", "formdata"):
                content_type = content_type or (
                    "application/x-www-form-urlencoded" if mode == "urlencoded" else "multipart/form-data")
                for p in body.get(mode, []) or []:
                    if isinstance(p, dict) and p.get("key") and not p.get("disabled"):
                        body_fields.append(str(p["key"]))
                        if p.get("type") == "file":
                            has_upload = True
                        else:
                            s = find_secret("body", str(p["key"]), p.get("value"))
                            if s:
                                secrets.append(s)
            elif mode == "graphql":
                body_fields = ["query", "variables"]
                content_type = content_type or "application/json"
            elif mode == "file":
                has_upload = True

        # ---- auth
        auth_type = "none"
        if auth:
            auth_type, auth_secrets = _auth_type_and_secrets(auth)
            secrets.extend(auth_secrets)
        if auth_type == "none":  # credentials sent via headers/query still count even if Postman auth is "No Auth"
            auth_type = classify_header_auth(raw_headers) or classify_query_auth(query_params) or "none"

        headers = {k: mask_if_secret(k, resolve_vars(v, self.variables)) for k, v in raw_headers.items()}
        self.endpoints.append(Endpoint(
            id="", name=str(item.get("name") or f"{method} {raw_clean}"), method=method, url=mask_url_secrets(url_resolved),
            path_params=path_params, query_params=dedupe(query_params), headers=headers,
            body_fields=dedupe(body_fields), auth_type=auth_type, folder=" / ".join(f for f in folder if f),
            body_content_type=content_type, has_file_upload=has_upload, source="postman", secrets=secrets,
        ))


def is_postman(data: Any) -> bool:
    return isinstance(data, dict) and isinstance(data.get("info"), dict) and "item" in data


def parse_postman(data: dict, env_vars: dict[str, str] | None = None) -> Collection:
    info = data.get("info")
    if not isinstance(info, dict):
        raise ParseError("Not a valid Postman collection: missing 'info' object.")
    schema = str(info.get("schema", ""))
    if schema and "collection/v2" not in schema:
        raise ParseError(f"Unsupported Postman schema '{schema}'.", code="UNSUPPORTED_VERSION",
                         hint="In Postman, export the collection as Collection v2.1.")
    items = data.get("item")
    if not isinstance(items, list):
        raise ParseError("Not a valid Postman collection: 'item' must be a list.")

    variables: dict[str, str] = {}  # values used to resolve {{vars}} (secrets already masked, placeholders skipped)
    variable_secrets: list[SecretRef] = []
    for v in data.get("variable", []) or []:
        if isinstance(v, dict) and v.get("key") and not v.get("disabled"):
            val = "" if v.get("value") is None else str(v["value"])
            rv = resolution_value(str(v["key"]), val)
            if rv is not None:
                variables[str(v["key"])] = rv
            s = find_secret("variable", str(v["key"]), val)
            if s:
                variable_secrets.append(s)

    if env_vars:
        variables.update(env_vars)  # environment values take precedence over collection variables
    w = _Walker(variables)
    root_auth = data.get("auth") if isinstance(data.get("auth"), dict) else None
    w.walk(items, [], root_auth)
    if not w.endpoints:
        raise ParseError("The Postman collection contains no requests.", code="EMPTY_COLLECTION",
                         hint="Add at least one request to the collection and export it again.")

    base = ""
    for key in ("baseUrl", "base_url", "baseURL", "host", "url"):
        if variables.get(key):
            base = variables[key]
            break
    if env_vars:
        w.warnings.append(f"Environment applied: {len(env_vars)} variable(s) available for resolving {{{{variables}}}}.")
    return Collection(
        name=str(info.get("name") or "Untitled collection"), source_type="postman", base_url=base,
        endpoints=w.endpoints, variable_secrets=variable_secrets, warnings=w.warnings,
    )
