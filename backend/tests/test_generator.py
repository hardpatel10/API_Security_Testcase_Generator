import json
import re

from backend.generator import analyze_collection, detect_traits, generate_test_cases
from backend.models import Endpoint
from backend.standards import ASVS, CWE, OWASP_API_LABELS, WSTG


def make(**kw) -> Endpoint:
    base = dict(id="EP-001", name="x", method="GET", url="https://api.example.com/things", auth_type="bearer")
    base.update(kw)
    return Endpoint(**base)


def titles(e: Endpoint) -> list[str]:
    return [t.title for t in generate_test_cases([e])]


def test_every_endpoint_gets_baseline_tests():
    ts = titles(make(auth_type="none"))
    for t in ("HTTP method tampering", "Security response headers", "CORS policy", "Verbose error messages", "TLS enforcement"):
        assert t in ts


def test_tests_depend_on_traits():
    plain = titles(make(url="https://a.com/ping", auth_type="none"))
    assert not any("BOLA" in t or "injection" in t.lower() for t in plain)
    assert "Confirm unauthenticated access is intended" in plain

    by_id = titles(make(url="https://a.com/users/{userId}", path_params=["userId"]))
    assert "BOLA: access another user's object" in by_id and "Object ID enumeration" in by_id
    assert "Tampered token handling" in by_id and "Low-privilege token on privileged function (BFLA)" in by_id

    body = titles(make(method="POST", body_fields=["name", "callbackUrl"], body_content_type="application/json"))
    for t in ("Mass assignment / unauthorized property update", "Malformed body and wrong content type", "Oversized payload",
              "SQL injection", "NoSQL injection", "Cross-site scripting (XSS) payloads", "Server-side request forgery (SSRF)"):
        assert t in body


def test_trait_detection():
    t = detect_traits(make(url="https://a.com/auth/login", method="POST", auth_type="none", body_fields=["email", "password"]))
    assert t.is_login and t.is_auth_flow and t.enumerates_users
    t = detect_traits(make(url="https://a.com/items", query_params=["page", "limit"]))
    assert t.is_list
    t = detect_traits(make(url="https://a.com/items/{itemId}", path_params=["itemId"]))
    assert not t.is_list and t.id_params
    t = detect_traits(make(method="GET", query_params=["redirect_url"]))
    assert t.redirect_params == ["redirect_url"] and t.url_params
    t = detect_traits(make(method="POST", has_file_upload=True))
    assert t.is_upload
    assert detect_traits(make(url="http://a.com/x")).plain_http


def test_auth_flow_and_upload_and_list_tests():
    login = titles(make(url="https://a.com/auth/login", method="POST", auth_type="none", body_fields=["email", "password"]))
    for t in ("Brute force / credential stuffing", "Rate limiting on authentication flow", "User enumeration"):
        assert t in login
    assert "File upload: extension and content-type bypass" in titles(make(method="POST", has_file_upload=True))
    lst = titles(make(url="https://a.com/users", query_params=["page"]))
    assert "Pagination abuse" in lst and "Excessive data exposure" in lst
    assert "Open redirect" in titles(make(query_params=["redirect_url"]))


def test_basic_auth_uses_credential_test_not_jwt():
    ts = titles(make(auth_type="basic"))
    assert "Invalid or revoked credential handling" in ts and "Tampered token handling" not in ts


def test_unique_ids_and_complete_mappings(postman, openapi):
    for coll in (postman, openapi):
        cases = generate_test_cases(coll.endpoints)
        assert len({c.id for c in cases}) == len(cases)
        ep_ids = {e.id for e in coll.endpoints}
        for c in cases:
            assert c.endpoint_id in ep_ids
            assert c.owasp_api in OWASP_API_LABELS
            assert c.cwe and c.asvs and c.wstg
            assert all(x in CWE for x in c.cwe), c.cwe
            assert all(x in ASVS for x in c.asvs), c.asvs
            assert all(x in WSTG for x in c.wstg), c.wstg
            assert c.how_to_test and c.test_data and c.expected_result
            assert c.status == "Not Started" and c.notes == ""
            assert c.severity in {"High", "Medium", "Low", "Info"}


def test_test_counts_vary_by_endpoint(postman):
    cases = generate_test_cases(postman.endpoints)
    per = {e.name: sum(1 for c in cases if c.endpoint_id == e.id) for e in postman.endpoints}
    assert per["Update user"] > per["Actuator health"]
    assert len(set(per.values())) > 3


def test_analyze_summary_consistency(postman):
    r = analyze_collection(postman)
    s = r.summary
    assert s.total_endpoints == len(r.endpoints) == 12
    assert s.total_test_cases == len(r.test_cases) == sum(s.test_cases_by_severity.values()) == sum(s.test_cases_by_owasp.values())
    assert s.test_cases_by_status["Not Started"] == len(r.test_cases)
    assert s.total_findings == len(r.findings) == sum(s.findings_by_severity.values())
    assert re.match(r"API\d+:2023 ", next(iter(s.test_cases_by_owasp)))


def test_no_real_secrets_in_output(postman):
    dump = json.dumps(analyze_collection(postman).model_dump())
    for secret in ("Passw0rd!123", "Sup3rSecret", "dummysignature", "abcd1234efgh5678", "admin123"):
        assert secret not in dump
