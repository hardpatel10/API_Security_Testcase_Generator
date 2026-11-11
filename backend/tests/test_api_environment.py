"""API tests for environment support and structured errors."""
import io
import json

from fastapi.testclient import TestClient
from openpyxl import load_workbook

from backend.app.main import MAX_UPLOAD_BYTES, app

client = TestClient(app)

RAW_ENV_SECRETS = ["Sup3rSecret!", "Qm7Lp2Xz9RvTa4KcWb8YdNe5HgFu1JsV", "c2lnbmF0dXJlLWZvci1kZW1vLW9ubHk"]

COLLECTION_WITH_VARS = json.dumps({"info": {"name": "Vars"}, "item": [
    {"name": "List users", "request": {"method": "GET", "url": "{{baseUrl}}/users?page=1",
                                       "header": [{"key": "Authorization", "value": "Bearer {{accessToken}}"}]}},
    {"name": "Delete", "request": {"method": "DELETE", "url": "{{baseUrl}}/users/:id"}}]}).encode()


def post_files(files: dict):
    return client.post("/api/analyze", files=files)


def f(name, content):
    return (name, content, "application/json")


def test_environment_only_upload_returns_friendly_422_with_findings(env_bytes):
    r = post_files({"file": f("env.json", env_bytes)})
    assert r.status_code == 422
    d = r.json()
    assert d["code"] == "ENVIRONMENT_ONLY"
    assert d["message"] == "This is a Postman environment file, not a collection. It has variables but no requests."
    assert d["hint"] == "In Postman, open the collection > ... > Export > Collection v2.1."
    a = d["analysis"]
    assert a["endpoints"] == [] and a["test_cases"] == [] and a["notice"]["code"] == "ENVIRONMENT_ONLY"
    assert a["findings"] and all(x["group"] == "Environment" and x["endpoint_id"] is None for x in a["findings"])
    assert a["summary"]["environment_findings"] == len(a["findings"])
    for secret in RAW_ENV_SECRETS:
        assert secret not in r.text
    assert "eyJh****" in r.text


def test_environment_only_via_environment_field(env_bytes):
    r = post_files({"environment": f("env.json", env_bytes)})
    assert r.status_code == 422 and r.json()["code"] == "ENVIRONMENT_ONLY" and r.json()["analysis"]["findings"]


def test_collection_plus_environment_resolves_and_reviews(env_bytes):
    r = post_files({"file": f("c.json", COLLECTION_WITH_VARS), "environment": f("e.json", env_bytes)})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["endpoints"][0]["url"] == "https://staging.demoshop.example.com/v1/users?page=1"
    assert d["test_cases"]
    assert d["environment"]["name"] == "Demo Shop - Staging" and d["environment"]["applied"] is True
    assert d["notice"] is None
    assert {"Environment", "Endpoint"} <= {x["group"] for x in d["findings"]}
    assert len({x["id"] for x in d["findings"]}) == len(d["findings"])
    for secret in RAW_ENV_SECRETS:
        assert secret not in r.text
    r2 = post_files({"file": f("c.json", COLLECTION_WITH_VARS)})  # without env the variable stays unresolved
    assert r2.json()["endpoints"][0]["url"].startswith("{{baseUrl}}") and r2.json()["environment"] is None


def test_files_in_wrong_slots_are_detected(env_bytes):
    r = post_files({"file": f("e.json", env_bytes), "environment": f("c.json", COLLECTION_WITH_VARS)})
    assert r.status_code == 200 and r.json()["environment"]["applied"]


def test_two_collections_rejected(postman_bytes):
    r = post_files({"file": f("a.json", postman_bytes), "environment": f("b.json", postman_bytes)})
    assert r.status_code == 422 and r.json()["code"] == "TWO_COLLECTIONS"


def test_structured_errors():
    r = post_files({"file": f("c.json", b'{\n "a": 1,\n "b": \n}')})
    d = r.json()
    assert r.status_code == 422 and d["code"] == "INVALID_SYNTAX" and d["line"] == 4 and d["hint"] and d["message"]
    r = post_files({"file": f("c.json", b'{"info": {"name": "x"}, "item": []}')})
    assert r.status_code == 422 and r.json()["code"] == "EMPTY_COLLECTION" and r.json()["hint"]
    r = post_files({"file": f("c.json", b'{"hello": "world"}')})
    assert r.json()["code"] == "UNRECOGNIZED_FORMAT" and "Swagger 2.0" in r.json()["message"]
    assert set(r.json()) >= {"code", "message", "hint"}


def test_413_is_structured():
    r = post_files({"file": f("c.json", b"{" + b" " * (MAX_UPLOAD_BYTES + 10) + b"}")})
    assert r.status_code == 413 and r.json()["code"] == "FILE_TOO_LARGE" and r.json()["hint"]


def test_size_limit_applies_to_both_files_combined(postman_bytes):
    pad = b" " * int(MAX_UPLOAD_BYTES * 0.6)
    r = post_files({"file": f("a.json", postman_bytes + pad), "environment": f("e.json", b'{"values": []}' + pad)})
    assert r.status_code == 413


def test_excel_includes_environment_sheet(env_bytes):
    analysis = post_files({"file": f("c.json", COLLECTION_WITH_VARS), "environment": f("e.json", env_bytes)}).json()
    x = client.post("/api/export", json={"analysis": analysis})
    wb = load_workbook(io.BytesIO(x.content))
    ws = wb["Environment Findings"]
    n_env = sum(1 for a in analysis["findings"] if a["group"] == "Environment")
    assert n_env > 0 and ws.max_row == n_env + 5
    dump = " ".join(str(c.value) for row in ws.iter_rows() for c in row if c.value)
    assert "eyJh****" in dump and all(s not in dump for s in RAW_ENV_SECRETS)
    assert wb["Static Findings"].max_row == len(analysis["findings"]) - n_env + 5
    summary = " ".join(str(c.value) for row in wb["Summary"].iter_rows() for c in row if c.value)
    assert "Environment findings" in summary and "Demo Shop - Staging (applied)" in summary


def test_environment_only_export_works(env_bytes):
    analysis = post_files({"file": f("e.json", env_bytes)}).json()["analysis"]
    x = client.post("/api/export", json={"analysis": analysis})
    assert x.status_code == 200
    assert load_workbook(io.BytesIO(x.content))["Endpoint Test Plan"].max_row == 5
