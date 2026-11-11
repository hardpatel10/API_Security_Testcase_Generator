import json

import pytest

from backend.parsers import ParseError, parse_bytes, parse_text
from backend.parsers.common import mask, is_placeholder, extract_path_params
from .conftest import ep_by_name


def test_mask():
    assert mask("eyJhbGciOiJIUzI1NiJ9") == "eyJh****"
    assert mask("abc") == "****"
    assert mask("Bearer eyJhbGciOiJIUzI1NiJ9") == "Bearer eyJh****"


def test_placeholders():
    assert is_placeholder("{{token}}")
    assert is_placeholder("Bearer {{token}}")
    assert is_placeholder("<your-token>")
    assert not is_placeholder("Sup3rSecret!")


def test_path_param_extraction():
    assert extract_path_params("/users/:id/orders/{orderId}") == ["id", "orderId"]
    assert extract_path_params("/{{baseUrl}}/x") == []


def test_postman_basic(postman):
    assert postman.name == "Demo Shop API (sample)"
    assert postman.source_type == "postman"
    assert len(postman.endpoints) == 12
    assert [e.id for e in postman.endpoints][:2] == ["EP-001", "EP-002"]


def test_postman_variable_resolution(postman):
    login = ep_by_name(postman, "Login")
    assert login.url == "https://api.demoshop.example.com/v1/auth/login"
    admin = ep_by_name(postman, "Admin dashboard (Basic auth)")
    assert admin.url.startswith("http://legacy.demoshop.example.com/admin")


def test_postman_auth_inheritance(postman):
    assert ep_by_name(postman, "List users").auth_type == "bearer"  # inherited from collection
    assert ep_by_name(postman, "Login").auth_type == "none"  # noauth override
    assert ep_by_name(postman, "Admin dashboard (Basic auth)").auth_type == "basic"


def test_postman_params_and_body(postman):
    lst = ep_by_name(postman, "List users")
    assert lst.query_params == ["page", "limit"]
    upd = ep_by_name(postman, "Update user")
    assert upd.path_params == ["userId"]
    assert {"role", "isAdmin"} <= set(upd.body_fields)
    assert upd.body_content_type == "application/json"
    assert ep_by_name(postman, "Upload avatar").has_file_upload
    assert ep_by_name(postman, "Update user").folder == "Users"


def test_postman_secrets_are_masked(postman):
    login = ep_by_name(postman, "Login")
    assert any(s.location == "body" and s.name == "password" and s.masked == "Pass****" for s in login.secrets)
    assert {s.name for s in postman.variable_secrets} == {"accessToken", "adminPassword"}
    track = ep_by_name(postman, "Track order (API key in query)")
    assert track.auth_type == "apikey-query"
    assert track.secrets[0].masked == "abcd****"
    dump = json.dumps(postman.model_dump())
    assert "Passw0rd!123" not in dump and "Sup3rSecret" not in dump and "dummysignature" not in dump


def test_openapi_basic(openapi):
    assert openapi.source_type == "openapi"
    assert openapi.name == "Library API (sample)"
    assert len(openapi.endpoints) == 7
    assert openapi.has_security_schemes is True
    e = ep_by_name(openapi, "Get a book")
    assert e.url == "https://library.example.com/api/books/{bookId}"
    assert e.path_params == ["bookId"]
    assert e.auth_type == "bearer"
    assert e.responses == ["200", "401"]


def test_openapi_body_refs_and_upload(openapi):
    create = ep_by_name(openapi, "Create a book")
    assert {"title", "price", "isAdmin", "publisher.webhookUrl"} <= set(create.body_fields)
    avatar = ep_by_name(openapi, "Upload member avatar")
    assert avatar.has_file_upload and avatar.auth_type == "apikey-query"
    assert ep_by_name(openapi, "Delete a book").auth_type == "none"
    login = ep_by_name(openapi, "Member login")
    assert login.secrets and login.secrets[0].masked == "hunt****"


def test_swagger2_json():
    doc = {
        "swagger": "2.0", "info": {"title": "Old API"}, "host": "old.example.com", "basePath": "/v1",
        "schemes": ["http"],
        "securityDefinitions": {"b": {"type": "basic"}},
        "paths": {"/pets/{id}": {"get": {"security": [{"b": []}], "parameters": [
            {"name": "id", "in": "path", "type": "string"}], "responses": {"200": {"description": "ok"}}}}},
    }
    c = parse_text(json.dumps(doc))
    assert c.source_type == "swagger"
    assert c.endpoints[0].url == "http://old.example.com/v1/pets/{id}"
    assert c.endpoints[0].auth_type == "basic"


@pytest.mark.parametrize("text,msg", [
    ("", "empty"),
    ("{not json", "not valid"),
    ("[1, 2]", "object"),
    ('{"hello": "world"}', "Unrecognized"),
    ('{"info": {"name": "x"}, "item": []}', "no requests"),
    ('{"openapi": "4.0.0", "info": {}, "paths": {}}', "Unsupported OpenAPI"),
    ('{"openapi": "3.0.0", "info": {"title": "t"}, "paths": {}}', "paths"),
    ('{"info": {"schema": "https://schema.getpostman.com/json/collection/v1.0.0/collection.json"}, "item": [{}]}', "Unsupported Postman"),
])
def test_invalid_inputs(text, msg):
    with pytest.raises(ParseError) as ei:
        parse_text(text)
    assert msg.lower() in str(ei.value).lower()


def test_non_utf8():
    with pytest.raises(ParseError):
        parse_bytes(b"\xff\xfe\x00bad")
