"""Concrete static-analysis rules."""
from __future__ import annotations

import re

from ..models import Collection, Endpoint, Finding
from .base import (
    STATE_CHANGING, WRITE_METHODS, Rule, endpoint_path, is_public_flow, path_segments,
)


class NoAuthRule(Rule):
    id = "no-auth"

    def match(self, ep: Endpoint) -> Finding | None:
        if ep.auth_type != "none" or ep.method in STATE_CHANGING:  # PUT/PATCH/DELETE handled by StateChangingNoAuthRule
            return None
        public = is_public_flow(ep)
        sev = "Low" if public else ("High" if ep.method == "POST" else "Medium")
        note = " (may be intentional for a login/public endpoint - confirm)" if public else ""
        return self.finding(
            ep.id, "No authentication defined" + note, f"{ep.method} {ep.url}: no auth, Authorization header or API key",
            sev, ["API2:2023", "CWE-306", "ASVS V4.1.1"],
            "Require authentication (e.g. OAuth2/JWT bearer) on every non-public endpoint and deny by default.")


class WeakAuthRule(Rule):
    id = "weak-auth"

    def match(self, ep: Endpoint) -> Finding | None:
        if ep.auth_type == "basic":
            return self.finding(
                ep.id, "Weak authentication: HTTP Basic auth", "auth type = Basic (credentials sent with every request)",
                "Medium", ["API2:2023", "CWE-522", "ASVS V3.5.2"],
                "Replace Basic auth with short-lived tokens (OAuth2/OIDC) and always enforce TLS.")
        if ep.auth_type == "apikey-query":
            keys = [q for q in ep.query_params if q.lower() in {"api_key", "apikey", "api-key", "key", "access_token", "token", "auth_token"}]
            return self.finding(
                ep.id, "Weak authentication: API key sent in the query string",
                f"query parameter(s): {', '.join(keys) or 'api key'}", "High",
                ["API2:2023", "CWE-598", "ASVS V13.1.3", "ASVS V8.3.1"],
                "Send API keys in a header (e.g. Authorization / X-API-Key); query strings are logged and cached.")
        return None


class HardcodedSecretRule(Rule):
    id = "hardcoded-secret"

    def match(self, ep: Endpoint) -> Finding | None:
        if not ep.secrets:
            return None
        ev = "; ".join(f"{s.location} '{s.name}' = {s.masked}" for s in ep.secrets[:6])
        if len(ep.secrets) > 6:
            ev += f"; +{len(ep.secrets) - 6} more"
        return self.finding(
            ep.id, "Hard-coded credential/secret in request", ev, "High",
            ["API2:2023", "CWE-798", "ASVS V2.10.4"],
            "Remove literal secrets from the collection; use environment variables/secret stores and rotate any exposed value.")

    def match_collection(self, collection: Collection) -> list[Finding]:
        if not collection.variable_secrets:
            return []
        ev = "; ".join(f"variable '{s.name}' = {s.masked}" for s in collection.variable_secrets)
        return [self.finding(
            None, "Hard-coded secret stored in collection variables", ev, "High",
            ["API2:2023", "CWE-798", "ASVS V2.10.4"],
            "Keep secrets in unshared environment/secret variables and rotate exposed values.")]


class PlainHttpRule(Rule):
    id = "plain-http"

    def match(self, ep: Endpoint) -> Finding | None:
        if not ep.url.lower().startswith("http://"):
            return None
        sev = "High" if ep.auth_type != "none" else "Medium"
        return self.finding(
            ep.id, "Endpoint uses plain HTTP (no TLS)", ep.url, sev,
            ["API8:2023", "CWE-319", "ASVS V9.1.1"],
            "Serve the API over HTTPS only, redirect/disable HTTP and enable HSTS.")


_SENSITIVE_URL_RE = re.compile(r"(token|passw(or)?d|pwd|secret|ssn|api[-_]?key|apikey|credit[-_]?card|cvv)", re.I)


class SensitiveDataInUrlRule(Rule):
    id = "sensitive-url"

    def match(self, ep: Endpoint) -> Finding | None:
        hits = [f"query '{q}'" for q in ep.query_params if _SENSITIVE_URL_RE.search(q)]
        hits += [f"path segment '{s}'" for s in path_segments(ep) if _SENSITIVE_URL_RE.search(s) and not s.startswith("{{")
                 and s.lower() not in {"token", "tokens", "password", "passwords"} and (s.startswith(":") or "{" in s)]
        if not hits:
            return None
        return self.finding(
            ep.id, "Sensitive data in URL", "; ".join(hits), "Medium",
            ["API8:2023", "CWE-598", "ASVS V8.3.1"],
            "Move sensitive values to the request body or headers; URLs end up in logs, browser history and referrers.")


_ADMIN_RE = re.compile(r"^(admin|administrator|debug|actuator|internal|management|console|phpinfo|_debug|_internal)$", re.I)


class AdminDebugPathRule(Rule):
    id = "admin-debug-path"

    def match(self, ep: Endpoint) -> Finding | None:
        segs = [s for s in path_segments(ep) if _ADMIN_RE.match(s)]
        if not segs:
            return None
        sev = "High" if ep.auth_type == "none" else "Medium"
        return self.finding(
            ep.id, "Admin/debug/internal path exposed", f"path contains: /{'/, /'.join(segs)}/ in {endpoint_path(ep)}", sev,
            ["API9:2023", "API8:2023", "CWE-489", "ASVS V14.3.2", "ASVS V4.3.1"],
            "Do not expose admin/debug/actuator/internal routes publicly; restrict by network, strong auth and disable in production.")


class StateChangingNoAuthRule(Rule):
    id = "state-change-no-auth"

    def match(self, ep: Endpoint) -> Finding | None:
        if ep.method not in STATE_CHANGING or ep.auth_type != "none":
            return None
        return self.finding(
            ep.id, f"State-changing {ep.method} request without authentication",
            f"{ep.method} {ep.url}: no authentication defined", "High",
            ["API2:2023", "API5:2023", "CWE-306", "ASVS V4.1.1"],
            "Require authentication and authorization for every PUT/PATCH/DELETE operation.")


_ID_PARAM_RE = re.compile(r"(^id$|_id$|[a-z]Id$|Id$|^uuid$|^guid$|_uuid$)")
_NUM_UUID_RE = re.compile(r"^(\d+|[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$")


def id_path_params(ep: Endpoint) -> list[str]:
    return [p for p in ep.path_params if _ID_PARAM_RE.search(p) or p.lower() in {"id", "uuid", "guid"}]


def literal_id_segments(ep: Endpoint) -> list[str]:
    return [s for s in path_segments(ep) if _NUM_UUID_RE.match(s)]


class BolaCandidateRule(Rule):
    id = "bola-candidate"

    def match(self, ep: Endpoint) -> Finding | None:
        ids = id_path_params(ep) + literal_id_segments(ep)
        if not ids:
            return None
        return self.finding(
            ep.id, "Object ID in path (BOLA candidate)", f"identifier(s) in path: {', '.join(ids)}", "Medium",
            ["API1:2023", "CWE-639", "ASVS V4.2.1"],
            "Enforce object-level authorization checks on every request; prefer unpredictable IDs (UUIDv4) as defense in depth.")


MASS_ASSIGN_FIELDS = {
    "role", "roles", "isadmin", "is_admin", "admin", "price", "status", "permissions", "balance", "verified",
    "isverified", "is_verified", "discount", "credit", "owner", "ownerid", "owner_id", "userid", "user_id", "isactive",
}


class MassAssignmentRule(Rule):
    id = "mass-assignment"

    def match(self, ep: Endpoint) -> Finding | None:
        if ep.method not in {"POST", "PUT", "PATCH"}:
            return None
        hits = [f for f in ep.body_fields if f.split(".")[-1].replace("[]", "").lower() in MASS_ASSIGN_FIELDS]
        if not hits:
            return None
        return self.finding(
            ep.id, "Mass-assignment risk fields in request body", f"sensitive field(s): {', '.join(hits)}", "Medium",
            ["API3:2023", "CWE-915", "ASVS V4.1.2"],
            "Bind only an explicit allow-list of client-writable properties; never accept role/price/status-style fields from clients.")


# ---- OpenAPI-only rules ----------------------------------------------------------------------------


class MissingSecuritySchemesRule(Rule):
    id = "missing-security-schemes"

    def match_collection(self, collection: Collection) -> list[Finding]:
        if collection.has_security_schemes is False:
            return [self.finding(
                None, "No securitySchemes defined in the OpenAPI document", "components.securitySchemes / securityDefinitions is empty",
                "High", ["API2:2023", "CWE-306", "ASVS V4.1.1"],
                "Declare securitySchemes and apply them via 'security' globally or per operation.")]
        return []


class NoRateLimitResponseRule(Rule):
    id = "no-429"

    def match(self, ep: Endpoint) -> Finding | None:
        if ep.source != "openapi" or "429" in ep.responses:
            return None
        return self.finding(
            ep.id, "No 429 (Too Many Requests) response documented", f"documented responses: {', '.join(ep.responses) or 'none'}",
            "Low", ["API4:2023", "CWE-770", "ASVS V11.1.4"],
            "Implement rate limiting and document the 429 response with Retry-After.")


class NoAuthErrorResponsesRule(Rule):
    id = "no-401-403"

    def match(self, ep: Endpoint) -> Finding | None:
        if ep.source != "openapi" or ep.auth_type == "none":
            return None
        if {"401", "403", "4XX", "4xx", "default"} & set(ep.responses):
            return None
        return self.finding(
            ep.id, "No 401/403 responses documented for a secured endpoint",
            f"documented responses: {', '.join(ep.responses) or 'none'}", "Low",
            ["API2:2023", "API5:2023", "CWE-285", "ASVS V4.1.1"],
            "Document and implement 401 (unauthenticated) and 403 (unauthorized) responses.")


ALL_RULES: list[Rule] = [
    NoAuthRule(), WeakAuthRule(), HardcodedSecretRule(), PlainHttpRule(), SensitiveDataInUrlRule(),
    AdminDebugPathRule(), StateChangingNoAuthRule(), BolaCandidateRule(), MassAssignmentRule(),
    MissingSecuritySchemesRule(), NoRateLimitResponseRule(), NoAuthErrorResponsesRule(),
]
