from backend.models import Collection, Endpoint, SecretRef
from backend.parsers import parse_bytes
from backend.rules import ALL_RULES, run_rules
from backend.rules.rules import (
    AdminDebugPathRule, BolaCandidateRule, HardcodedSecretRule, MassAssignmentRule, MissingSecuritySchemesRule,
    NoAuthErrorResponsesRule, NoAuthRule, NoRateLimitResponseRule, PlainHttpRule, SensitiveDataInUrlRule,
    StateChangingNoAuthRule, WeakAuthRule,
)
from backend.standards import ASVS, CWE, OWASP_API

from .conftest import SAMPLES


def ep(**kw) -> Endpoint:
    base = dict(id="EP-001", name="x", method="GET", url="https://api.example.com/things", auth_type="bearer")
    base.update(kw)
    return Endpoint(**base)


def test_no_auth():
    f = NoAuthRule().match(ep(auth_type="none", method="POST", url="https://a.com/orders"))
    assert f and f.severity == "High" and "CWE-306" in f.standard_refs
    assert NoAuthRule().match(ep(auth_type="bearer")) is None
    login = NoAuthRule().match(ep(auth_type="none", method="POST", url="https://a.com/auth/login"))
    assert login and login.severity == "Low"
    assert NoAuthRule().match(ep(auth_type="none", method="DELETE")) is None  # handled by state-changing rule


def test_weak_auth():
    assert WeakAuthRule().match(ep(auth_type="basic")).severity == "Medium"
    f = WeakAuthRule().match(ep(auth_type="apikey-query", query_params=["api_key"]))
    assert f.severity == "High" and "api_key" in f.evidence_masked
    assert WeakAuthRule().match(ep(auth_type="bearer")) is None


def test_hardcoded_secret_is_masked():
    e = ep(secrets=[SecretRef(location="header", name="Authorization", masked="Bear****")])
    f = HardcodedSecretRule().match(e)
    assert f and "Bear****" in f.evidence_masked and f.severity == "High"
    assert HardcodedSecretRule().match(ep()) is None
    c = Collection(name="c", source_type="postman",
                   variable_secrets=[SecretRef(location="variable", name="pw", masked="abcd****")])
    f = HardcodedSecretRule().match_collection(c)[0]
    assert f.endpoint_id is None and f.group == "Collection"


def test_plain_http():
    assert PlainHttpRule().match(ep(url="http://a.com/x")).severity == "High"
    assert PlainHttpRule().match(ep(url="http://a.com/x", auth_type="none")).severity == "Medium"
    assert PlainHttpRule().match(ep(url="https://a.com/x")) is None


def test_sensitive_data_in_url():
    f = SensitiveDataInUrlRule().match(ep(query_params=["page", "password"]))
    assert f and "password" in f.evidence_masked
    assert SensitiveDataInUrlRule().match(ep(query_params=["page"])) is None


def test_admin_paths():
    assert AdminDebugPathRule().match(ep(url="https://a.com/admin/users"))
    assert AdminDebugPathRule().match(ep(url="{{baseUrl}}/actuator/health", auth_type="none")).severity == "High"
    assert AdminDebugPathRule().match(ep(url="https://a.com/administrators-guide")) is None


def test_state_changing_without_auth():
    assert StateChangingNoAuthRule().match(ep(method="PUT", auth_type="none"))
    assert StateChangingNoAuthRule().match(ep(method="GET", auth_type="none")) is None
    assert StateChangingNoAuthRule().match(ep(method="PATCH", auth_type="bearer")) is None


def test_bola_candidate():
    assert BolaCandidateRule().match(ep(url="https://a.com/users/{userId}", path_params=["userId"]))
    assert BolaCandidateRule().match(ep(url="https://a.com/users/42"))
    assert BolaCandidateRule().match(ep(url="https://a.com/users/{slug}", path_params=["slug"])) is None


def test_mass_assignment():
    f = MassAssignmentRule().match(ep(method="POST", body_fields=["name", "profile.isAdmin", "price"]))
    assert f and "profile.isAdmin" in f.evidence_masked
    assert MassAssignmentRule().match(ep(method="GET", body_fields=["role"])) is None


def test_openapi_rules():
    c = Collection(name="c", source_type="openapi", has_security_schemes=False)
    assert MissingSecuritySchemesRule().match_collection(c)
    c.has_security_schemes = True
    assert MissingSecuritySchemesRule().match_collection(c) == []
    assert NoRateLimitResponseRule().match(ep(source="openapi", responses=["200"]))
    assert NoRateLimitResponseRule().match(ep(source="openapi", responses=["200", "429"])) is None
    assert NoRateLimitResponseRule().match(ep(source="postman")) is None
    assert NoAuthErrorResponsesRule().match(ep(source="openapi", responses=["200"]))
    assert NoAuthErrorResponsesRule().match(ep(source="openapi", responses=["200", "401"])) is None


def test_run_rules_on_samples(postman, openapi):
    pf = run_rules(postman)
    assert [f.id for f in pf][:2] == ["F-001", "F-002"]
    issues = " | ".join(f.issue for f in pf)
    for expected in ("Hard-coded", "plain HTTP", "Admin/debug", "BOLA", "Mass-assignment", "query string", "Basic auth",
                     "State-changing", "No authentication"):
        assert expected in issues, expected
    of = run_rules(openapi)
    assert any("429" in f.issue for f in of) and any("401/403" in f.issue for f in of)


def test_all_rule_refs_exist_in_catalog():
    assert len(ALL_RULES) >= 5
    findings = []
    for n in ("sample-postman.json", "sample-openapi.yaml"):
        findings += run_rules(parse_bytes((SAMPLES / n).read_bytes()))
    for f in findings:
        for r in f.standard_refs:
            if r.startswith("CWE-"):
                assert r in CWE, r
            elif r.startswith("ASVS "):
                assert r.split()[1] in ASVS, r
            else:
                assert r.split(":")[0] in OWASP_API, r
