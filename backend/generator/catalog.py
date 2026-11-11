"""Security test templates. Which ones apply to an endpoint is decided by its traits (see traits.py).

All test data are safe, generic example payloads intended for AUTHORIZED testing only.
"""
from __future__ import annotations

import json
from typing import Any

from ..models import Endpoint
from .traits import Traits


def _t(title: str, description: str, category: str, steps: list[str], data: str, expected: str, severity: str,
       api: str, cwe: list[str], asvs: list[str], wstg: list[str]) -> dict[str, Any]:
    return dict(title=title, description=description, category=category, how_to_test=steps, test_data=data,
                expected_result=expected, severity=severity, api=api, cwe=cwe, asvs=asvs, wstg=wstg)


def _target(ep: Endpoint) -> str:
    return f"{ep.method} {ep.url}"


def _auth_hint(ep: Endpoint) -> str:
    return {
        "bearer": "Authorization: Bearer <valid_token>", "oauth2": "Authorization: Bearer <valid_oauth_token>",
        "basic": "Authorization: Basic <base64(user:pass)>", "apikey-header": "<API key header>: <valid_key>",
        "apikey-query": "?<api_key_param>=<valid_key>", "apikey-cookie": "Cookie: <session/api key>",
    }.get(ep.auth_type, "<valid credentials>")


def _body(ep: Endpoint, override: dict[str, Any] | None = None, only: list[str] | None = None, limit: int = 6) -> str:
    """Small JSON example built from the endpoint's top-level body fields."""
    fields = [f for f in ep.body_fields if "." not in f and "[" not in f]
    if only:
        fields = only
    body: dict[str, Any] = {f: "string" for f in fields[:limit]}
    if override:
        body.update(override)
    return json.dumps(body, ensure_ascii=False)


def _first_input(ep: Endpoint, t: Traits) -> str:
    return t.inputs[0] if t.inputs else "<input>"


def _inject_target(ep: Endpoint, t: Traits) -> str:
    return ("body field(s)" if t.has_body and any("." not in f for f in ep.body_fields) else "query parameter(s)") \
        + f": {', '.join(t.inputs[:5])}"


# ---------------------------------------------------------------------------------------------------
# Every endpoint
# ---------------------------------------------------------------------------------------------------

def common_tests(ep: Endpoint, t: Traits) -> list[dict]:
    tgt = _target(ep)
    return [
        _t("HTTP method tampering",
           "Check that the endpoint only accepts the HTTP methods it is designed for and that unexpected methods "
           "(e.g. TRACE, PUT, DELETE, method-override headers) cannot bypass access controls.",
           "Security Misconfiguration",
           [f"Send the same request to {ep.url} using each of GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS and TRACE.",
            "Record the status code and Allow header for every method.",
            "Retry with X-HTTP-Method-Override / X-Method-Override: DELETE on a POST request.",
            "Confirm that unsupported methods are rejected and authorization is enforced for all accepted methods."],
           f"Methods to try: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS, TRACE; header X-HTTP-Method-Override: DELETE (baseline: {tgt})",
           "Unsupported methods return 405 (or 404) with a correct Allow header; TRACE is disabled; method-override headers are ignored.",
           "Medium", "API8", ["CWE-650"], ["V13.2.1", "V14.5.1"], ["WSTG-CONF-06"]),
        _t("Security response headers",
           "Verify that responses carry baseline security headers and do not leak server/framework details.",
           "Security Misconfiguration",
           [f"Send a valid request to {ep.url} and inspect the response headers.",
            "Check for Strict-Transport-Security, X-Content-Type-Options: nosniff, Cache-Control: no-store (for sensitive data) and a restrictive Content-Security-Policy.",
            "Check that Server / X-Powered-By headers do not disclose product versions."],
           "Inspect headers: Strict-Transport-Security, X-Content-Type-Options, Cache-Control, Content-Security-Policy, Server, X-Powered-By",
           "HSTS and nosniff are present, sensitive responses are not cacheable, and no version information is disclosed.",
           "Low", "API8", ["CWE-693"], ["V14.4.4", "V14.4.5"], ["WSTG-CONF-14", "WSTG-CONF-07"]),
        _t("CORS policy",
           "Verify that cross-origin requests are only allowed from trusted origins and credentials are not exposed to arbitrary sites.",
           "Security Misconfiguration",
           [f"Send {tgt} with the header Origin: https://evil.example.",
            "Repeat with Origin: null and with a sub-domain of a trusted origin (e.g. https://trusted.example.evil.example).",
            "Send an OPTIONS pre-flight request and inspect Access-Control-Allow-Origin / -Credentials / -Methods.",
            "Confirm the origin is never reflected together with Access-Control-Allow-Credentials: true."],
           "Origin: https://evil.example | Origin: null | OPTIONS with Access-Control-Request-Method: DELETE",
           "Untrusted origins (including 'null') are not allowed; a wildcard is never combined with credentials.",
           "Medium", "API8", ["CWE-942"], ["V14.5.3"], ["WSTG-CLNT-07"]),
        _t("Verbose error messages",
           "Verify that error responses do not leak stack traces, SQL errors, file paths, framework names or internal hostnames.",
           "Security Misconfiguration",
           [f"Send requests to {ep.url} that should fail: invalid values, missing required fields, wrong content type, unsupported method.",
            "Inspect the response bodies and headers of each error for stack traces, internal paths, SQL fragments or version strings.",
            "Confirm errors use a consistent generic format with a correlation id."],
           "Trigger errors with: empty body, invalid JSON, 10,000-character string, reserved characters (' \" < > % \\ ;)",
           "Errors return generic messages (no stack traces, queries, paths or internal details).",
           "Low", "API8", ["CWE-209"], ["V7.4.1", "V14.3.2"], ["WSTG-ERRH-01"]),
        _t("TLS enforcement",
           "Verify the endpoint is only reachable over TLS with modern protocol versions and that HTTP is not served or is redirected.",
           "Transport Security",
           [f"Request the endpoint over plain HTTP: {ep.url.replace('https://', 'http://', 1)}.",
            "Confirm the request is refused or redirected (301/308) to HTTPS and no sensitive data is returned over HTTP.",
            "Scan the TLS configuration (e.g. with testssl.sh / sslyze) for TLS 1.0/1.1, weak ciphers and certificate problems."],
           "Plain-HTTP request; TLS scan of the API host",
           "Only TLS 1.2+ with strong ciphers is accepted; plain HTTP is disabled or redirected; HSTS is enabled.",
           "High" if t.plain_http else "Medium", "API8", ["CWE-319"], ["V9.1.1"], ["WSTG-CRYP-01", "WSTG-CONF-07"]),
    ]


# ---------------------------------------------------------------------------------------------------
# Authentication / authorization
# ---------------------------------------------------------------------------------------------------

def auth_tests(ep: Endpoint, t: Traits) -> list[dict]:
    tgt = _target(ep)
    out: list[dict] = []
    if not t.has_auth:
        out.append(_t(
            "Confirm unauthenticated access is intended",
            "No authentication is defined for this endpoint. Verify whether it is meant to be public and that it exposes no sensitive data or actions.",
            "Authentication",
            [f"Send {tgt} without any credentials.",
             "If the call succeeds, review the response for personal, internal or business-sensitive data.",
             "Confirm with the API owner that anonymous access is by design; otherwise log a finding."],
            "Request with no Authorization header, cookies or API key",
            "Anonymous access is only possible for endpoints that are intentionally public and return no sensitive data.",
            "High" if t.state_changing and not t.is_auth_flow else "Medium", "API2", ["CWE-306"], ["V4.1.1"], ["WSTG-ATHN-04"]))
        return out
    hint = _auth_hint(ep)
    out.append(_t(
        "Access without authentication token",
        "Verify the endpoint rejects requests that carry no credentials, an empty credential or a malformed credential.",
        "Authentication",
        [f"Send a valid request ({tgt}) with the credential removed entirely.",
         "Repeat with an empty value (e.g. 'Authorization: Bearer ') and with a malformed value.",
         "Confirm no data is returned and no state is changed."],
        f"Remove or blank: {hint}",
        "401 Unauthorized with a generic body; no data returned and no side effects.",
        "High", "API2", ["CWE-306", "CWE-287"], ["V4.1.1"], ["WSTG-ATHN-04"]))
    if t.token_based:
        out.append(_t(
            "Expired token handling",
            "Verify that expired or revoked tokens are rejected.",
            "Authentication",
            [f"Obtain a valid token, wait until it expires (or use an already expired/revoked token).",
             f"Send {tgt} using the expired token.",
             "Also test a token issued before logout / password change."],
            "Authorization: Bearer <expired_or_revoked_token>",
            "401 Unauthorized; expired and revoked tokens are never accepted.",
            "Medium", "API2", ["CWE-613"], ["V3.5.3"], ["WSTG-SESS-10"]))
        out.append(_t(
            "Tampered token handling",
            "Verify the server validates token signatures and claims (alg=none, modified claims, wrong key/issuer/audience).",
            "Authentication",
            [f"Decode the JWT and modify a claim (e.g. user id or role); keep the original signature.",
             "Re-submit with the header changed to alg=none and an empty signature.",
             "Re-submit a token signed with a different key and one with a wrong 'iss'/'aud'.",
             f"Send each variant to {tgt}."],
            "Authorization: Bearer <token with modified payload> | alg=none token | token signed with another key",
            "All tampered tokens are rejected with 401; the server pins the signing algorithm and validates iss/aud/exp.",
            "High", "API2", ["CWE-347"], ["V3.5.3"], ["WSTG-SESS-10"]))
    else:
        out.append(_t(
            "Invalid or revoked credential handling",
            "Verify that wrong, rotated or revoked credentials (API key / basic auth) are rejected without leaking details.",
            "Authentication",
            [f"Send {tgt} with a wrong credential, then with a revoked/rotated credential.",
             "Compare responses and timing with a missing credential.",
             "Confirm the response does not reveal whether the username/key exists."],
            f"Invalid value for: {hint}",
            "401 Unauthorized with an identical generic response for all invalid credentials.",
            "Medium", "API2", ["CWE-287"], ["V3.5.2"], ["WSTG-ATHN-04"]))
    sev = "High" if (t.state_changing or t.is_admin_path) else "Medium"
    out.append(_t(
        "Low-privilege token on privileged function (BFLA)",
        "Verify that a valid but low-privileged user cannot call functions reserved for higher roles.",
        "Authorization",
        [f"Authenticate as a regular (low-privilege) user and as an administrator; capture both credentials.",
         f"Send {tgt} with the low-privilege credential.",
         "Try the same request with horizontal variants (another tenant/role) and with HTTP method changes.",
         "Compare against the admin result; the low-privilege call must be refused."],
        f"Credential of a low-privilege user: {hint}",
        "403 Forbidden for roles without permission; authorization is enforced server-side per function.",
        sev, "API5", ["CWE-285", "CWE-862"], ["V4.1.1", "V4.1.3", "V13.1.4"], ["WSTG-ATHZ-02", "WSTG-ATHZ-03"]))
    return out


def admin_tests(ep: Endpoint, t: Traits) -> list[dict]:
    if not t.is_admin_path:
        return []
    return [_t(
        "Admin/debug/internal route exposure",
        "The path looks administrative, debug or internal. Verify it is not reachable from untrusted networks or by unprivileged users.",
        "Inventory & Exposure",
        [f"Send {_target(ep)} from an external network without credentials, then with a normal user's credentials.",
         "Check whether the route reveals configuration, environment variables, heap dumps or health details.",
         "Confirm the route is disabled in production or protected by network controls and strong authentication."],
        "Unauthenticated request; low-privilege request; sibling paths (/actuator/env, /debug/vars, /admin/users)",
        "Admin/debug/internal routes are not exposed publicly and require strong authentication and authorization.",
        "High", "API9", ["CWE-489", "CWE-284"], ["V4.3.1", "V14.3.2"], ["WSTG-CONF-05"])]


# ---------------------------------------------------------------------------------------------------
# Object identifiers
# ---------------------------------------------------------------------------------------------------

def id_tests(ep: Endpoint, t: Traits) -> list[dict]:
    if not t.id_params:
        return []
    ids = ", ".join(t.id_params[:3])
    sev = "High"
    return [
        _t("BOLA: access another user's object",
           "Verify that object identifiers cannot be swapped to read or modify objects belonging to other users or tenants.",
           "Authorization",
           [f"Create two test users (A and B) and an object owned by each. Note the identifier(s): {ids}.",
            f"As user A, send {_target(ep)} using user B's object identifier.",
            "Repeat for every supported method (read, update, delete) and for nested/related resources.",
            "Confirm user A can neither see nor change user B's object."],
           f"Replace {ids} with an identifier owned by another user (e.g. <victim_id>)",
           "403 Forbidden or 404 Not Found; no data of other users is returned and nothing is modified.",
           sev, "API1", ["CWE-639", "CWE-284"], ["V4.2.1", "V13.1.4"], ["WSTG-ATHZ-04"]),
        _t("Object ID enumeration",
           "Verify identifiers are not easily guessable and that responses do not reveal which identifiers exist.",
           "Authorization",
           [f"Collect several valid identifiers for {ids} and check whether they are sequential or otherwise predictable.",
            "Request neighbouring and non-existent identifiers with your own credentials.",
            "Compare status codes, bodies and response times for 'exists but forbidden' versus 'does not exist'.",
            "Confirm requests are rate limited."],
           f"Sequence such as {ids}=1,2,3,... ; random UUIDs; non-existent ids",
           "Identifiers are unpredictable (e.g. UUIDv4) and forbidden/non-existent objects return indistinguishable responses.",
           "Medium", "API1", ["CWE-639", "CWE-204"], ["V4.2.1"], ["WSTG-ATHZ-04"]),
    ]


# ---------------------------------------------------------------------------------------------------
# Request body / inputs
# ---------------------------------------------------------------------------------------------------

def body_tests(ep: Endpoint, t: Traits) -> list[dict]:
    out: list[dict] = []
    tgt = _target(ep)
    if t.has_body:
        mass_hit = [f for f in ep.body_fields if f.split(".")[-1].lower() in {
            "role", "roles", "isadmin", "is_admin", "admin", "price", "status", "permissions", "balance", "verified",
            "isverified", "is_verified", "discount", "credit", "owner", "ownerid", "owner_id", "userid", "user_id", "isactive"}]
        out.append(_t(
            "Mass assignment / unauthorized property update",
            "Verify the API ignores or rejects properties the client must not control (roles, price, status, ownership, internal flags).",
            "Authorization",
            [f"Send a valid {tgt} request and note the accepted properties.",
             "Add privileged/read-only properties (role, isAdmin, price, status, owner_id, id) to the body.",
             "Check the response and re-read the object to see whether any injected property was persisted.",
             "Confirm unknown/privileged properties are rejected or ignored."],
            _body(ep, {"role": "admin", "isAdmin": True, "price": 0, "status": "approved"}),
            "Privileged and read-only properties are ignored or rejected (400/403) and are not persisted.",
            "High" if mass_hit else "Medium", "API3", ["CWE-915"], ["V4.1.2", "V5.1.3"], ["WSTG-INPV-20"]))
        out.append(_t(
            "Malformed body and wrong content type",
            "Verify the parser rejects syntactically invalid bodies and unexpected content types cleanly.",
            "Input Validation",
            [f"Send {tgt} with truncated JSON, an unclosed brace and duplicated keys.",
             "Change Content-Type to text/plain, application/xml and multipart/form-data while keeping the body.",
             "Confirm each request is rejected with a clean 400/415 and no stack trace."],
            '{"a": | {"a":1,"a":2} | Content-Type: application/xml with a JSON body',
            "400 Bad Request or 415 Unsupported Media Type with a generic error; no internal details leaked.",
            "Low", "API10", ["CWE-20", "CWE-209"], ["V13.1.5", "V13.2.2"], ["WSTG-ERRH-01"]))
        out.append(_t(
            "Oversized payload",
            "Verify request size limits protect the service from memory/CPU exhaustion.",
            "Resource Consumption",
            [f"Send {tgt} with a body of 1 MB, then 10 MB, then a deeply nested JSON structure (e.g. 1,000 levels).",
             "Send very long string values (100,000 characters) and arrays with many elements.",
             "Observe status codes and latency; confirm the server stops processing early."],
            "Strings of 100,000 'A' characters; arrays with 10,000 items; nesting depth 1,000 (use a controlled, small-scale test)",
            "413 Payload Too Large (or 400) is returned quickly; the service remains responsive.",
            "Medium", "API4", ["CWE-770", "CWE-400"], ["V12.1.1", "V11.1.4"], ["WSTG-BUSL-05"]))
    if t.inputs:
        inputs = ", ".join(t.inputs[:5])
        out.append(_t(
            "Wrong data types and boundary values",
            "Verify input validation enforces types, ranges and formats on every parameter.",
            "Input Validation",
            [f"For each input ({inputs}) send a wrong type (string instead of number, array instead of string, object, null, boolean).",
             "Send boundary values: 0, -1, 2147483648, very large numbers, empty strings and very long strings.",
             "Confirm invalid input is rejected with 400/422 and valid ranges are enforced."],
            _body(ep, {_first_input(ep, t): ["unexpected", {"nested": True}]}) if t.has_body else
            f"{_first_input(ep, t)}[]=1&{_first_input(ep, t)}=-1 | 2147483648 | null | ''",
            "Invalid types/ranges are rejected with 400/422; the server never errors with 500.",
            "Low", "API10", ["CWE-20"], ["V5.1.3", "V5.1.4", "V13.2.2"], ["WSTG-BUSL-01"]))
        where = _inject_target(ep, t)
        out.append(_t(
            "SQL injection",
            "Verify that user-controlled input is not concatenated into SQL queries.",
            "Injection",
            [f"Identify injection points: {where}.",
             "Send a single quote and the boolean payloads below in each input, one at a time.",
             "Look for SQL errors, changed result sets or measurable time differences (use a harmless delay payload only on systems you are authorized to test).",
             "Confirm the application uses parameterized queries."],
            "' | ' OR '1'='1 | 1' AND '1'='2 | 1; SELECT 1--",
            "Inputs are treated as data: no SQL errors, no changed logic, consistent responses.",
            "High", "API10", ["CWE-89"], ["V5.3.4"], ["WSTG-INPV-05"]))
        out.append(_t(
            "NoSQL injection",
            "Verify that operators in JSON/query input are not interpreted by a NoSQL database.",
            "Injection",
            [f"Identify injection points: {where}.",
             'Replace string values with operator objects, e.g. {"$ne": null} or {"$gt": ""}.',
             "For query strings try field[$ne]=x style parameters.",
             "Confirm authentication and filters cannot be bypassed."],
            '{"' + _first_input(ep, t) + '": {"$ne": null}}  |  ' + _first_input(ep, t) + "[$ne]=x",
            "Operator syntax is rejected or treated as literal data; filters and logins cannot be bypassed.",
            "High", "API10", ["CWE-943"], ["V5.3.4"], ["WSTG-INPV-05"]))
        out.append(_t(
            "Cross-site scripting (XSS) payloads",
            "Verify that script payloads are not reflected or stored unencoded in responses consumed by browsers.",
            "Injection",
            [f"Submit the payload below in each input ({inputs}).",
             "Retrieve the data again (including through list/detail endpoints and exports) and inspect the response.",
             "Check Content-Type is correct (application/json) and that output is encoded where rendered in HTML."],
            "<script>alert(1)</script> | \"><img src=x onerror=alert(1)>",
            "Payloads are stored/returned as inert data (encoded or rejected); responses use the correct Content-Type.",
            "Medium", "API10", ["CWE-79"], ["V5.3.3"], ["WSTG-INPV-01", "WSTG-INPV-02"]))
    return out


# ---------------------------------------------------------------------------------------------------
# URL / host parameters, lists, auth flows, uploads
# ---------------------------------------------------------------------------------------------------

def url_tests(ep: Endpoint, t: Traits) -> list[dict]:
    out: list[dict] = []
    if t.url_params:
        p = ", ".join(t.url_params[:3])
        out.append(_t(
            "Server-side request forgery (SSRF)",
            "A parameter accepts a URL/host. Verify the server cannot be made to request internal or unintended resources.",
            "SSRF",
            [f"Identify the URL-type parameter(s): {p}.",
             "Submit a URL pointing to a collaborator/out-of-band host you control and confirm whether the server calls it.",
             "Submit loopback, private-range and link-local addresses, alternative encodings (decimal/hex/IPv6) and redirects to internal hosts.",
             "Confirm an allow-list of schemes, hosts and ports is enforced and responses are not reflected."],
            "https://collaborator.example.net/probe | http://127.0.0.1:80/ | http://169.254.169.254/ | http://[::1]/ | file:///etc/hostname",
            "Non-allow-listed destinations are rejected; no outbound request is made to internal addresses.",
            "High", "API7", ["CWE-918"], ["V5.2.6"], ["WSTG-INPV-19"]))
    if t.redirect_params:
        p = ", ".join(t.redirect_params[:3])
        out.append(_t(
            "Open redirect",
            "A parameter controls a redirect/return target. Verify redirects only go to allow-listed destinations.",
            "Input Validation",
            [f"Identify the redirect parameter(s): {p}.",
             "Set it to an external absolute URL, a protocol-relative URL (//evil.example) and encoded variants.",
             "Follow the response and confirm the Location header never points to an untrusted origin."],
            "https://evil.example | //evil.example | /\\evil.example | https://trusted.example@evil.example",
            "Only relative paths or allow-listed destinations are accepted; others are rejected.",
            "Medium", "API8", ["CWE-601"], ["V5.1.5"], ["WSTG-CLNT-04"]))
    return out


def list_tests(ep: Endpoint, t: Traits) -> list[dict]:
    if not t.is_list:
        return []
    return [
        _t("Pagination abuse",
           "Verify that pagination parameters are bounded so a single request cannot dump or exhaust large data sets.",
           "Resource Consumption",
           [f"Send {_target(ep)} with limit/page_size set to 0, -1, 100000 and 2147483647.",
            "Use very large offsets/pages and negative values.",
            "Confirm a maximum page size is enforced and response size/latency stay bounded."],
           "limit=0 | limit=-1 | limit=100000 | limit=2147483647 | offset=-1 | page=99999999",
           "A server-side maximum page size is enforced (e.g. capped or 400); invalid values are rejected.",
           "Medium", "API4", ["CWE-770", "CWE-1284"], ["V11.1.4"], ["WSTG-BUSL-05"]),
        _t("Excessive data exposure",
           "Verify list responses return only the properties the caller is allowed to see (no password hashes, internal ids, PII, tokens).",
           "Data Exposure",
           [f"Call {_target(ep)} as a low-privilege user and review every property in the response.",
            "Compare returned properties with what the UI/documentation needs.",
            "Check for filtering/sorting parameters that reveal hidden fields (e.g. sort=password, fields=*)."],
           "Review response properties; try fields=*, expand=all, sort=<sensitive_field>, filter[<sensitive_field>]=x",
           "Only necessary, authorized properties are returned; sensitive fields are never exposed or filterable.",
           "Medium", "API3", ["CWE-213", "CWE-200"], ["V4.1.3", "V4.2.1"], ["WSTG-ATHZ-04"]),
    ]


def flow_tests(ep: Endpoint, t: Traits) -> list[dict]:
    if not t.is_auth_flow:
        return []
    out = [
        _t("Rate limiting on authentication flow",
           "Verify the endpoint throttles repeated requests per account, IP and device.",
           "Resource Consumption",
           [f"Send {_target(ep)} 50-100 times in one minute with valid and invalid data (test account only).",
            "Watch for 429 Too Many Requests, Retry-After headers or temporary blocks.",
            "Try rotating headers such as X-Forwarded-For to confirm limits cannot be bypassed."],
           "Burst of 100 requests/min; X-Forwarded-For: 203.0.113.<n>",
           "429 (with Retry-After) is returned after a small number of attempts; limits cannot be bypassed via headers.",
           "Medium", "API4", ["CWE-799", "CWE-770"], ["V11.1.4", "V2.2.1"], ["WSTG-BUSL-05"]),
    ]
    if t.is_login or t.is_otp or t.is_reset:
        out.insert(0, _t(
            "Brute force / credential stuffing",
            "Verify that repeated failed attempts (passwords, OTP, reset tokens) trigger lockout or throttling.",
            "Authentication",
            [f"Using a test account, send {_target(ep)} repeatedly with wrong secrets (e.g. 20 attempts).",
             "Verify lockout, progressive delay or CAPTCHA is applied and the correct secret is rejected while locked.",
             "Confirm OTP/reset codes are limited in attempts and expire quickly."],
            "20+ failed attempts with invalid password/OTP for one test account",
            "Account/IP is throttled or locked after a small number of failures; OTP codes expire and are single use.",
            "High", "API2", ["CWE-307"], ["V2.2.1", "V2.8.1"], ["WSTG-ATHN-03"]))
    if t.enumerates_users:
        out.append(_t(
            "User enumeration",
            "Verify responses, status codes and timing do not reveal whether an account exists.",
            "Authentication",
            [f"Send {_target(ep)} with an existing and a non-existent identifier (email/username).",
             "Compare status codes, messages, response length and timing.",
             "Confirm messages are generic (e.g. 'If the account exists, an email was sent')."],
            "existing: known test user | non-existent: unknown-user-<random>@example.com",
            "Identical response (status, body, timing) regardless of account existence.",
            "Medium", "API2", ["CWE-204"], ["V2.2.1", "V7.4.1"], ["WSTG-IDNT-04"]))
    if t.is_reset or t.is_otp:
        out.append(_t(
            "Reset token / OTP lifetime and reuse",
            "Verify reset links/OTPs expire, are single use and are bound to the requesting user.",
            "Authentication",
            [f"Request a reset/OTP, use it once successfully, then try to reuse it on {_target(ep)}.",
             "Wait beyond the advertised lifetime and retry.",
             "Request a second code and confirm the first becomes invalid.",
             "Try using user A's code for user B's account."],
            "Used code; expired code; superseded code; code of a different user",
            "Codes are single use, short-lived, invalidated by newer codes and bound to one account.",
            "Medium", "API2", ["CWE-613", "CWE-307"], ["V2.5.6", "V2.8.1"], ["WSTG-ATHN-09"]))
    return out


def upload_tests(ep: Endpoint, t: Traits) -> list[dict]:
    if not t.is_upload:
        return []
    return [
        _t("File upload: extension and content-type bypass",
           "Verify the server validates the real file type and does not trust the extension or Content-Type header.",
           "File Upload",
           [f"Upload a harmless text file renamed to .jpg/.png and one with a double extension (test.php.jpg) to {_target(ep)}.",
            "Change the Content-Type of the part (e.g. image/png for a text file) and use mixed-case or trailing-dot extensions.",
            "Verify disallowed types are rejected, files are stored outside the web root with random names and are not executable."],
           "Files: test.txt renamed test.jpg | test.php.jpg | test.JpG. | EICAR-style harmless test file; Content-Type: image/png",
           "Only allow-listed types are accepted after content inspection; uploaded files are never executed.",
           "High", "API8", ["CWE-434"], ["V12.2.1"], ["WSTG-BUSL-08", "WSTG-BUSL-09"]),
        _t("File upload: size limit",
           "Verify maximum file size and count limits protect storage and processing capacity.",
           "File Upload",
           [f"Upload a file just below, exactly at and above the documented limit to {_target(ep)}.",
            "Upload many files in parallel (small number) and a zero-byte file.",
            "Confirm over-limit uploads are rejected early with 413 and do not consume disk/memory."],
           "Files of limit-1, limit and limit+1 bytes; 0 bytes; 5 parallel uploads",
           "Over-limit uploads return 413 promptly; limits are enforced server-side.",
           "Medium", "API4", ["CWE-770", "CWE-400"], ["V12.1.1"], ["WSTG-BUSL-09"]),
    ]


BUILDERS = [auth_tests, admin_tests, id_tests, body_tests, url_tests, list_tests, flow_tests, upload_tests, common_tests]
