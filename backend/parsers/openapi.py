"""OpenAPI 3.x / Swagger 2.0 parser."""
from __future__ import annotations

import re
from typing import Any

from ..models import Collection, Endpoint, SecretRef
from .common import ParseError, dedupe, extract_path_params, find_secret, mask_if_secret

METHODS = ["get", "post", "put", "patch", "delete", "head", "options", "trace"]


def is_openapi(data: Any) -> bool:
    return isinstance(data, dict) and ("openapi" in data or "swagger" in data)


class _Spec:
    def __init__(self, data: dict):
        self.data = data

    def deref(self, node: Any) -> Any:
        for _ in range(10):
            if isinstance(node, dict) and isinstance(node.get("$ref"), str):
                ref = node["$ref"]
                if not ref.startswith("#/"):
                    return {}  # external refs unsupported
                cur: Any = self.data
                for part in ref[2:].split("/"):
                    part = part.replace("~1", "/").replace("~0", "~")
                    cur = cur.get(part) if isinstance(cur, dict) else None
                    if cur is None:
                        return {}
                node = cur
            else:
                break
        return node

    def schema_fields(self, schema: Any, prefix: str = "", depth: int = 0,
                      leaves: list | None = None, seen: tuple = ()) -> list[str]:
        schema = self.deref(schema)
        if not isinstance(schema, dict) or depth > 4:
            return []
        key = id(schema)
        if key in seen:
            return []
        seen = seen + (key,)
        out: list[str] = []
        for sub in schema.get("allOf", []) or []:
            out += self.schema_fields(sub, prefix, depth, leaves, seen)
        for sub in (schema.get("oneOf") or schema.get("anyOf") or [])[:1]:
            out += self.schema_fields(sub, prefix, depth, leaves, seen)
        props = schema.get("properties")
        if isinstance(props, dict):
            for name, sub in props.items():
                full = f"{prefix}.{name}" if prefix else name
                out.append(full)
                sub_d = self.deref(sub)
                if isinstance(sub_d, dict):
                    if leaves is not None:
                        ex = sub_d.get("example", sub_d.get("default"))
                        if ex is not None:
                            leaves.append((name, ex))
                    out += self.schema_fields(sub_d, full, depth + 1, leaves, seen)
        if schema.get("type") == "array" and "items" in schema:
            out += self.schema_fields(schema["items"], f"{prefix}[]" if prefix else "[]", depth + 1, leaves, seen)
        return out

    def is_file_schema(self, schema: Any, depth: int = 0) -> bool:
        schema = self.deref(schema)
        if not isinstance(schema, dict) or depth > 3:
            return False
        if schema.get("type") == "file" or (schema.get("type") == "string" and schema.get("format") in ("binary", "byte")):
            return True
        if any(self.is_file_schema(s, depth + 1) for s in (schema.get("properties") or {}).values()):
            return True
        if "items" in schema:
            return self.is_file_schema(schema["items"], depth + 1)
        return False


def _auth_from_scheme(scheme: Any) -> str:
    if not isinstance(scheme, dict):
        return "other"
    t = str(scheme.get("type", "")).lower()
    if t == "http":
        s = str(scheme.get("scheme", "")).lower()
        return "basic" if s == "basic" else "bearer" if s == "bearer" else "other"
    if t == "basic":  # swagger 2.0
        return "basic"
    if t == "apikey":
        loc = str(scheme.get("in", "header")).lower()
        return {"query": "apikey-query", "cookie": "apikey-cookie"}.get(loc, "apikey-header")
    if t in ("oauth2", "openidconnect"):
        return "oauth2"
    return "other"


def parse_openapi(data: dict) -> Collection:
    is_swagger = "swagger" in data
    version = str(data.get("swagger") if is_swagger else data.get("openapi"))
    if is_swagger and not version.startswith("2."):
        raise ParseError(f"Unsupported Swagger version '{version}'. Only Swagger 2.0 is supported.", code="UNSUPPORTED_VERSION",
                         hint="Convert the document to Swagger 2.0 or OpenAPI 3.x.")
    if not is_swagger and not version.startswith("3."):
        raise ParseError(f"Unsupported OpenAPI version '{version}'. Only 3.x is supported.", code="UNSUPPORTED_VERSION",
                         hint="Convert the document to OpenAPI 3.x or Swagger 2.0.")
    info = data.get("info")
    if not isinstance(info, dict):
        raise ParseError("Invalid OpenAPI document: missing 'info' object.")
    paths = data.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise ParseError("Invalid OpenAPI document: 'paths' is missing or empty. It defines no requests.",
                         code="EMPTY_COLLECTION", hint="Define at least one path with an operation.")

    spec = _Spec(data)
    warnings: list[str] = []

    # ---- base URL(s)
    servers: list[str] = []
    if is_swagger:
        host = data.get("host", "")
        base_path = data.get("basePath", "") or ""
        schemes = data.get("schemes") or (["https"] if host else [])
        for sc in schemes:
            servers.append(f"{sc}://{host}{base_path}" if host else base_path)
        if not servers:
            servers = [base_path]
    else:
        for s in data.get("servers", []) or []:
            if isinstance(s, dict) and s.get("url"):
                url = str(s["url"])
                for vn, vd in (s.get("variables") or {}).items():
                    url = url.replace("{" + vn + "}", str((vd or {}).get("default", "")))
                servers.append(url)
    base = (servers[0] if servers else "").rstrip("/")
    insecure = [s for s in servers[1:] if s.lower().startswith("http://")]
    if insecure:
        warnings.append(f"Additional plain-HTTP server(s) declared: {', '.join(insecure)}")

    # ---- security schemes
    schemes_def = (data.get("securityDefinitions") if is_swagger
                   else (data.get("components") or {}).get("securitySchemes")) or {}
    global_security = data.get("security")

    endpoints: list[Endpoint] = []
    for path, item in paths.items():
        item = spec.deref(item)
        if not isinstance(item, dict):
            continue
        for m in METHODS:
            op = item.get(m)
            if not isinstance(op, dict):
                continue
            params = []
            seen_params: set[tuple] = set()
            for p in (op.get("parameters") or []) + (item.get("parameters") or []):  # op overrides path-level
                p = spec.deref(p)
                if isinstance(p, dict) and p.get("name"):
                    k = (p.get("in"), p["name"])
                    if k not in seen_params:
                        seen_params.add(k)
                        params.append(p)

            path_params = [p["name"] for p in params if p.get("in") == "path"]
            for n in extract_path_params(path):
                if n not in path_params:
                    path_params.append(n)
            query_params = [p["name"] for p in params if p.get("in") == "query"]
            headers: dict[str, str] = {}
            secrets: list[SecretRef] = []
            for p in params:
                if p.get("in") in ("header", "query"):
                    sch = spec.deref(p.get("schema")) or {}
                    ex = p.get("example", p.get("default", sch.get("example", sch.get("default") if isinstance(sch, dict) else None)))
                    s = find_secret(p["in"], p["name"], ex)
                    if s:
                        secrets.append(s)
                    if p["in"] == "header":
                        headers[p["name"]] = mask_if_secret(p["name"], "" if ex is None else str(ex))

            # ---- body
            body_fields: list[str] = []
            content_type = None
            has_upload = False
            leaves: list = []
            if is_swagger:
                consumes = op.get("consumes") or data.get("consumes") or []
                content_type = consumes[0] if consumes else None
                for p in params:
                    if p.get("in") == "body":
                        body_fields += spec.schema_fields(p.get("schema"), leaves=leaves)
                        content_type = content_type or "application/json"
                    elif p.get("in") == "formData":
                        body_fields.append(p["name"])
                        if p.get("type") == "file":
                            has_upload = True
                        content_type = content_type or ("multipart/form-data" if has_upload else "application/x-www-form-urlencoded")
            else:
                rb = spec.deref(op.get("requestBody"))
                content = (rb or {}).get("content") if isinstance(rb, dict) else None
                if isinstance(content, dict) and content:
                    content_type = next(iter(content))
                    for ct, media in content.items():
                        sch = (media or {}).get("schema")
                        if ct == content_type:
                            body_fields += spec.schema_fields(sch, leaves=leaves)
                        if spec.is_file_schema(sch) or ct.startswith("multipart/form-data") and spec.is_file_schema(sch):
                            has_upload = True
                        if "octet-stream" in ct:
                            has_upload = True
            for name, val in leaves:
                s = find_secret("body", name, val)
                if s:
                    secrets.append(s)

            # ---- auth
            sec = op["security"] if "security" in op else global_security
            auth_type = "none"
            if isinstance(sec, list):
                for req in sec:
                    if isinstance(req, dict) and req:
                        name = next(iter(req))
                        auth_type = _auth_from_scheme(schemes_def.get(name)) if name in schemes_def else "other"
                        break

            responses = [str(k) for k in (op.get("responses") or {}).keys()]
            name = op.get("summary") or op.get("operationId") or f"{m.upper()} {path}"
            tags = op.get("tags") or []
            endpoints.append(Endpoint(
                id="", name=str(name), method=m.upper(), url=f"{base}{path}",
                path_params=dedupe(path_params), query_params=dedupe(query_params), headers=headers,
                body_fields=dedupe(body_fields), auth_type=auth_type, folder=str(tags[0]) if tags else "",
                body_content_type=content_type, has_file_upload=has_upload, responses=responses,
                source="openapi", secrets=secrets,
            ))

    if not endpoints:
        raise ParseError("The OpenAPI document defines no operations under 'paths'.", code="EMPTY_COLLECTION",
                         hint="Define at least one operation (get, post, ...) under a path.")
    return Collection(
        name=str(info.get("title") or "Untitled API"), source_type="swagger" if is_swagger else "openapi",
        base_url=base, endpoints=endpoints, has_security_schemes=bool(schemes_def), warnings=warnings,
    )
