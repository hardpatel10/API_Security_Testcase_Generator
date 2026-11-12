"""Guards for the Vercel "services" deployment config (cannot be exercised without Vercel, so check consistency)."""
import importlib
import json
from pathlib import Path

from fastapi import FastAPI

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
BUILD_KEYS = {"functions", "installCommand", "buildCommand", "devCommand", "ignoreCommand", "outputDirectory", "framework"}


def test_services_mode_has_no_top_level_build_keys():
    assert "services" in CONFIG
    assert not (BUILD_KEYS & set(CONFIG)), "build/runtime keys are invalid at the top level in services mode"


def test_public_routing_order_api_first_then_frontend_catch_all():
    rewrites = CONFIG["rewrites"]
    assert [r["source"] for r in rewrites] == ["/api/(.*)", "/(.*)"]  # most specific first, catch-all last
    assert rewrites[0]["destination"] == {"service": "backend"}
    assert rewrites[1]["destination"] == {"service": "frontend"}
    for r in rewrites:
        assert r["destination"]["service"] in CONFIG["services"]


def test_backend_entrypoint_resolves_to_the_fastapi_app():
    svc = CONFIG["services"]["backend"]
    assert svc["framework"] == "fastapi" and svc["root"] == "."
    module, _, attr = svc["entrypoint"].partition(":")
    app = getattr(importlib.import_module(module), attr)
    assert isinstance(app, FastAPI)


def test_every_api_route_lives_under_the_public_api_prefix():
    """A service receives the original request path, so the app's own routes must start with /api."""
    from backend.app.main import app
    paths = {r.path for r in app.routes if getattr(r, "methods", None)}
    app_paths = {p for p in paths if p not in {"/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}}
    assert app_paths and all(p.startswith("/api/") for p in app_paths), app_paths


def test_frontend_service_and_calls_are_same_origin():
    fe = CONFIG["services"]["frontend"]
    assert fe["root"] == "frontend" and (ROOT / fe["root"] / "package.json").exists()
    assert "bindings" not in fe  # the browser calls /api on the same domain; no service-to-service calls exist
    src = (ROOT / "frontend" / "src" / "api.ts").read_text(encoding="utf-8")
    assert '"/api/analyze"' in src and '"/api/export"' in src and "http://" not in src


def test_vercelignore_does_not_exclude_the_frontend_package_manifest():
    lines = [ln.strip() for ln in (ROOT / ".vercelignore").read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#")]
    assert "package.json" not in lines and "package-lock.json" not in lines  # un-anchored entries match frontend/ too
    assert "/package.json" in lines
