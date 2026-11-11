import json

from backend.parsers import build_environment, load_document
from backend.rules import review_environment
from backend.standards import ASVS, CWE, OWASP_API


def env_of(values, **kw):
    return build_environment(load_document(json.dumps({"name": "e", "values": values, **kw}).encode()))


def v(key, value, type="default", **kw):
    return {"key": key, "value": value, "type": type, "enabled": True, **kw}


def issues(findings):
    return " | ".join(f.issue for f in findings)


def test_sample_environment_findings(env_bytes):
    f = review_environment(build_environment(load_document(env_bytes)))
    assert f and all(x.group == "Environment" and x.endpoint_id is None for x in f)
    text = issues(f)
    assert "plain-HTTP" in text and "service-role" in text and "type 'default'" in text and "Real-looking" in text
    sev = {x.issue: x.severity for x in f}
    assert sev["Environment variable 'localUrl' uses a plain-HTTP URL (local development host)"] == "Low"
    assert sev["Environment variable 'legacyUrl' uses a plain-HTTP URL"] == "Medium"
    assert any(x.severity == "High" and "supabaseServiceRoleKey" in x.issue for x in f)
    assert all(x.standard_refs and x.remediation and x.id for x in f)


def test_placeholders_and_empty_values_are_not_findings():
    f = review_environment(env_of([
        v("lawyerPassword", "<lawyer password>"), v("adminToken", "<token>"), v("apiKey", ""), v("secret", "{{other}}"),
        v("serviceRoleKey", "<service role key>"), v("password", "string"),
    ]))
    assert f == []


def test_disabled_variables_ignored():
    assert review_environment(env_of([v("password", "Sup3rSecret!", enabled=False)])) == []


def test_secret_name_with_default_type_is_medium_but_secret_type_is_not():
    f = review_environment(env_of([v("clientSecret", "abcd-1234-efgh"), v("api_key", "xyz-98765-abc", type="secret")]))
    by = {x.issue: x for x in f}
    flagged = [x for x in f if "type 'default'" in x.issue]
    assert len(flagged) == 1 and flagged[0].severity == "Medium" and "clientSecret" in flagged[0].issue
    assert not any("api_key" in x.issue for x in f)


def test_service_role_admin_root_are_high():
    f = review_environment(env_of([v("SERVICE_ROLE_KEY", "abcdef123456", type="secret"), v("rootPassword", "hunter2hunter2"),
                                   v("adminKey", "k-12345678", type="secret")]))
    assert len([x for x in f if x.severity == "High" and "Privileged" in x.issue]) == 3


def test_jwt_role_claim_detected_regardless_of_name(env_bytes):
    data = json.loads(env_bytes)
    jwt = next(x["value"] for x in data["values"] if x["key"] == "supabaseServiceRoleKey")
    f = review_environment(env_of([v("anonKey2", jwt, type="secret")]))
    assert any("role claim 'service_role'" in x.evidence_masked for x in f)


def test_secret_values_masked_and_never_raw(env_bytes):
    f = review_environment(build_environment(load_document(env_bytes)))
    dump = json.dumps([x.model_dump() for x in f])
    raw = json.loads(env_bytes)["values"]
    for item in raw:
        if item["key"] in ("accessToken", "adminPassword", "supabaseServiceRoleKey", "paymentApiKey"):
            assert item["value"] not in dump
            assert item["value"][:4] + "****" in dump
    assert "eyJh****" in dump and "Sup3****" in dump and "Qm7L****" in dump


def test_real_looking_values_detected_by_shape():
    f = review_environment(env_of([v("misc1", "sk_" + "live_" + "4eC39HqLyjWDarjtT1zdp7dc"), v("misc2", "Zx9fQ2LmA8vTr3KpWb7YdNc5HgEu1JsX"),
                                   v("collectionId", "5f8d0d55b54764421b7156c3"), v("ref", "123e4567-e89b-12d3-a456-426614174000"),
                                   v("userEmail", "tester@example.com")]))
    flagged = {x.evidence_masked.split(" ")[1].strip("'") for x in f}
    assert flagged == {"misc1", "misc2"}


def test_http_urls_credentials_stripped():
    f = review_environment(env_of([v("svc", "http://user:p4ss@internal.example.com/x?token=abcd1234efgh")]))
    ev = f[0].evidence_masked
    assert "p4ss" not in ev and "abcd1234efgh" not in ev and f[0].severity == "Medium"


def test_all_refs_exist_in_catalog(env_bytes):
    for x in review_environment(build_environment(load_document(env_bytes))):
        for r in x.standard_refs:
            if r.startswith("CWE-"):
                assert r in CWE
            elif r.startswith("ASVS "):
                assert r.split()[1] in ASVS
            else:
                assert r.split(":")[0] in OWASP_API
