from pathlib import Path

import pytest

from backend.parsers import parse_bytes

SAMPLES = Path(__file__).resolve().parents[2] / "frontend" / "public" / "samples"


@pytest.fixture(scope="session")
def postman_bytes() -> bytes:
    return (SAMPLES / "sample-postman.json").read_bytes()


@pytest.fixture(scope="session")
def openapi_bytes() -> bytes:
    return (SAMPLES / "sample-openapi.yaml").read_bytes()


@pytest.fixture()
def postman(postman_bytes):
    return parse_bytes(postman_bytes)


@pytest.fixture()
def openapi(openapi_bytes):
    return parse_bytes(openapi_bytes)


def ep_by_name(coll, name):
    return next(e for e in coll.endpoints if e.name == name)


@pytest.fixture(scope="session")
def env_bytes() -> bytes:
    return (SAMPLES / "sample-postman-environment.json").read_bytes()
