import json

import pytest

from backend.parsers import ParseError, build_collection, build_environment, load_document, parse_bytes, resolution_variables


def err(content) -> ParseError:
    with pytest.raises(ParseError) as ei:
        load_document(content if isinstance(content, bytes) else content.encode())
    return ei.value


def test_detection_order_and_kinds(postman_bytes, openapi_bytes, env_bytes):
    assert load_document(postman_bytes).kind == "postman"
    assert load_document(env_bytes).kind == "environment"
    assert load_document(openapi_bytes).kind == "openapi"
    assert load_document(b'{"_postman_variable_scope": "globals"}').kind == "environment"
    assert load_document(b'{"swagger": "2.0", "info": {}, "paths": {}}').kind == "openapi"


def test_environment_only_raises_friendly_error(env_bytes):
    with pytest.raises(ParseError) as ei:
        parse_bytes(env_bytes)
    e = ei.value
    assert e.code == "ENVIRONMENT_ONLY"
    assert e.message == "This is a Postman environment file, not a collection. It has variables but no requests."
    assert e.hint == "In Postman, open the collection > ... > Export > Collection v2.1."


def test_invalid_json_reports_line_and_column():
    e = err('{\n  "a": 1,\n  "b": \n}')
    assert e.code == "INVALID_SYNTAX" and e.line == 4 and e.column and "line 4" in e.message


def test_invalid_yaml_reports_location():
    e = err("openapi: 3.0.0\ninfo: [unclosed\npaths: {}\n")
    assert e.code == "INVALID_SYNTAX" and e.line and "YAML" in e.message


def test_empty_collection():
    with pytest.raises(ParseError) as ei:
        parse_bytes(b'{"info": {"name": "x"}, "item": []}')
    assert ei.value.code == "EMPTY_COLLECTION" and ei.value.hint
    with pytest.raises(ParseError) as ei:
        parse_bytes(b'{"openapi": "3.0.0", "info": {"title": "t"}, "paths": {}}')
    assert ei.value.code == "EMPTY_COLLECTION"


def test_unrecognized_lists_supported_formats():
    for content in ('{"hello": "world"}', "[1, 2]", "just some text"):
        e = err(content)
        assert e.code == "UNRECOGNIZED_FORMAT" and "Postman Collection v2.1" in e.message and "OpenAPI 3.x" in e.message


def collection(url="{{baseUrl}}/users", header=None):
    return json.dumps({"info": {"name": "c"}, "item": [{"name": "r", "request": {
        "method": "GET", "url": url, "header": header or []}}]}).encode()


def test_environment_resolves_variables(env_bytes):
    env = build_environment(load_document(env_bytes))
    doc = load_document(collection("{{baseUrl}}/users?api_key={{paymentApiKey}}", [
        {"key": "X-Token", "value": "{{accessToken}}"}, {"key": "X-Pw", "value": "{{lawyerPassword}}"}]))
    c = build_collection(doc, env)
    ep = c.endpoints[0]
    assert ep.url.startswith("https://staging.demoshop.example.com/v1/users")
    assert "Qm7Lp2Xz9RvTa4KcWb8YdNe5HgFu1JsV" not in ep.url and "Qm7L****" in ep.url
    assert ep.headers["X-Token"].endswith("****") and "eyJhbGci" not in json.dumps(ep.model_dump())
    assert ep.headers["X-Pw"] == "{{lawyerPassword}}"  # placeholder values are never substituted
    assert any("Environment applied" in w for w in c.warnings)


def test_environment_overrides_collection_variables():
    data = {"info": {"name": "c"}, "variable": [{"key": "baseUrl", "value": "https://old.example.com"}],
            "item": [{"name": "r", "request": {"method": "GET", "url": "{{baseUrl}}/x"}}]}
    env = build_environment(load_document(b'{"name":"e","values":[{"key":"baseUrl","value":"https://new.example.com"}]}'))
    assert build_collection(load_document(json.dumps(data).encode()), env).endpoints[0].url == "https://new.example.com/x"
    assert build_collection(load_document(json.dumps(data).encode())).endpoints[0].url == "https://old.example.com/x"


def test_resolution_variables_skip_placeholders_disabled_and_empty():
    env = build_environment(load_document(json.dumps({"values": [
        {"key": "a", "value": "<some value>"}, {"key": "b", "value": ""}, {"key": "c", "value": "ok"},
        {"key": "d", "value": "hidden", "enabled": False}]}).encode()))
    assert resolution_variables(env) == {"c": "ok"}
