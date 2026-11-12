import io

import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook

from backend.app.main import MAX_UPLOAD_BYTES, app

from .conftest import SAMPLES

client = TestClient(app)


def post_file(content: bytes, name="c.json", field="file"):
    return client.post("/api/analyze", files={field: (name, content, "application/octet-stream")})


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}


def test_analyze_postman(postman_bytes):
    r = post_file(postman_bytes)
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(d) == {"collection", "endpoints", "findings", "test_cases", "summary", "environment", "notice"}
    assert d["collection"]["name"] == "Demo Shop API (sample)"
    assert d["summary"]["total_endpoints"] == len(d["endpoints"]) == 12
    assert d["summary"]["total_test_cases"] == len(d["test_cases"]) > 100
    tc = d["test_cases"][0]
    for k in ("id", "endpoint_id", "title", "description", "category", "how_to_test", "test_data", "expected_result",
              "severity", "owasp_api", "cwe", "asvs", "wstg", "status", "notes"):
        assert k in tc
    for k in ("id", "endpoint_id", "issue", "evidence_masked", "severity", "standard_refs", "remediation"):
        assert k in d["findings"][0]
    assert "Passw0rd!123" not in r.text and "dummysignature" not in r.text


def test_analyze_openapi_yaml(openapi_bytes):
    r = post_file(openapi_bytes, "api.yaml")
    assert r.status_code == 200 and r.json()["collection"]["source_type"] == "openapi"


def test_analyze_invalid_file():
    r = post_file(b'{"hello": "world"}')
    assert r.status_code == 422 and "Unrecognized format" in r.json()["detail"]
    assert post_file(b"").status_code == 422
    assert post_file(b"\xff\xfe\x00").status_code == 422


def test_analyze_missing_file_and_wrong_type():
    assert client.post("/api/analyze", files={"other": (None, "text")}).status_code == 400
    r = client.post("/api/analyze", json={"a": 1})
    assert r.status_code == 400


def test_analyze_too_large_returns_413():
    r = post_file(b"{" + b" " * (MAX_UPLOAD_BYTES + 10) + b"}")
    assert r.status_code == 413
    assert "4 MB" in r.json()["detail"]


def test_upload_just_under_limit_is_processed(postman_bytes):
    padded = postman_bytes + b" " * (MAX_UPLOAD_BYTES - len(postman_bytes) - 10)
    assert post_file(padded).status_code == 200


def test_yaml_alias_bomb_rejected():
    bomb = "a: &a [x]\n" + "\n".join(f"k{i}: *a" for i in range(300)) + "\n"
    r = post_file(bomb.encode(), "bomb.yaml")
    assert r.status_code == 422 and "aliases" in r.json()["detail"]


def test_export_all_and_filtered(postman_bytes):
    analysis = post_file(postman_bytes).json()
    analysis["test_cases"][0]["status"] = "Fail"
    analysis["test_cases"][0]["notes"] = "found in staging"
    r = client.post("/api/export", json={"analysis": analysis})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert "attachment" in r.headers["content-disposition"] and r.headers["content-disposition"].endswith('.xlsx"')
    ws = load_workbook(io.BytesIO(r.content))["Endpoint Test Plan"]
    assert ws.max_row == len(analysis["test_cases"]) + 5
    assert ws.cell(6, 13).value == "Fail" and ws.cell(6, 14).value == "found in staging"

    ids = [t["id"] for t in analysis["test_cases"][:3]]
    r2 = client.post("/api/export", json={"analysis": analysis, "test_case_ids": ids})
    assert "filtered" in r2.headers["content-disposition"]
    assert load_workbook(io.BytesIO(r2.content))["Endpoint Test Plan"].max_row == 8


def test_export_validation_errors():
    assert client.post("/api/export", json={"nope": 1}).status_code == 422
    assert client.post("/api/export", content=b"not json", headers={"content-type": "application/json"}).status_code == 422


def test_export_rejects_invalid_status(postman_bytes):
    analysis = post_file(postman_bytes).json()
    analysis["test_cases"][0]["status"] = "Maybe"
    assert client.post("/api/export", json={"analysis": analysis}).status_code == 422

