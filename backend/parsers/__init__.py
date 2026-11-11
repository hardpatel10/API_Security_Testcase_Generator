"""Parsers: Postman collection / Postman environment / OpenAPI / Swagger -> internal models."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import yaml

from ..models import Collection, Environment
from .common import ParseError
from .environment import is_environment, parse_environment, resolution_variables
from .openapi import is_openapi, parse_openapi
from .postman import is_postman, parse_postman

__all__ = [
    "ParseError", "Document", "load_document", "build_collection", "build_environment", "parse_bytes",
    "parse_text", "parse_postman", "parse_openapi", "parse_environment", "resolution_variables",
]

SUPPORTED_FORMATS = "Postman Collection v2.1 (JSON), OpenAPI 3.x (JSON or YAML), Swagger 2.0 (JSON or YAML)"
_YAML_ALIAS_RE = re.compile(r"(?m)(?:^|[\s:\[,-])\*[A-Za-z0-9_-]+")
MAX_YAML_ALIASES = 200


@dataclass
class Document:
    kind: str  # postman | environment | openapi
    data: dict[str, Any]


def _unrecognized(extra: str = "") -> ParseError:
    return ParseError(
        f"Unrecognized format{extra}. Supported formats: {SUPPORTED_FORMATS}.", code="UNRECOGNIZED_FORMAT",
        hint="Export your API as a Postman Collection v2.1 or provide an OpenAPI/Swagger document.")


def load_document(content: bytes) -> Document:
    """Decode, parse (JSON/YAML) and classify an uploaded file. Detection order: collection, environment, OpenAPI."""
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as e:
        raise ParseError("The file is not valid UTF-8 text.", code="INVALID_SYNTAX",
                         hint="Save or export the file as UTF-8 JSON or YAML.") from e
    stripped = text.strip()
    if not stripped:
        raise ParseError("The uploaded file is empty.", code="EMPTY_FILE", hint="Choose a file that has content.")
    try:
        if stripped[0] in "{[":
            data = json.loads(stripped)
        else:
            if len(_YAML_ALIAS_RE.findall(stripped)) > MAX_YAML_ALIASES:  # alias-expansion bomb guard
                raise ParseError("The YAML file uses too many aliases (*name) and cannot be processed safely.",
                                 code="INVALID_SYNTAX", hint="Expand or remove the YAML aliases.")
            data = yaml.safe_load(stripped)
    except json.JSONDecodeError as e:
        raise ParseError(f"The file is not valid JSON or YAML: invalid JSON at line {e.lineno}, column {e.colno} "
                         f"({e.msg}).", code="INVALID_SYNTAX", line=e.lineno, column=e.colno,
                         hint="Check for a missing comma, quote or bracket near that position, or re-export the file.") from e
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        line, col = (mark.line + 1, mark.column + 1) if mark else (None, None)
        where = f" at line {line}, column {col}" if line else ""
        problem = getattr(e, "problem", None) or str(e).splitlines()[0]
        raise ParseError(f"The file is not valid JSON or YAML: invalid YAML{where} ({problem}).",
                         code="INVALID_SYNTAX", line=line, column=col,
                         hint="Check the indentation and quoting near that position.") from e
    except RecursionError as e:
        raise ParseError("The file is nested too deeply to be processed.", code="INVALID_SYNTAX") from e
    if not isinstance(data, dict):
        raise _unrecognized(": the file must contain a JSON/YAML object")

    if is_postman(data):
        return Document("postman", data)
    if is_environment(data):
        return Document("environment", data)
    if is_openapi(data):
        return Document("openapi", data)
    raise _unrecognized()


def build_collection(doc: Document, env: Environment | None = None) -> Collection:
    if doc.kind == "postman":
        coll = parse_postman(doc.data, resolution_variables(env))
    elif doc.kind == "openapi":
        coll = parse_openapi(doc.data)
    else:
        raise ParseError("This is a Postman environment file, not a collection. It has variables but no requests.",
                         code="ENVIRONMENT_ONLY", hint="In Postman, open the collection > ... > Export > Collection v2.1.")
    for i, ep in enumerate(coll.endpoints, 1):
        ep.id = f"EP-{i:03d}"
    return coll


def build_environment(doc: Document) -> Environment:
    return parse_environment(doc.data)


def parse_bytes(content: bytes) -> Collection:
    """Parse a single uploaded file as a collection (raises ENVIRONMENT_ONLY for environment files)."""
    return build_collection(load_document(content))


def parse_text(text: str) -> Collection:
    return parse_bytes(text.encode("utf-8"))
