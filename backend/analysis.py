"""Orchestrates one analysis from the uploaded file(s): detect, pair collection + environment, analyze."""
from __future__ import annotations

from .generator import ENVIRONMENT_ONLY_HINT, ENVIRONMENT_ONLY_MESSAGE, analyze_collection, analyze_environment_only
from .models import AnalysisResult
from .parsers import ParseError, build_collection, build_environment, load_document


class EnvironmentOnlyError(ParseError):
    """Only an environment file was supplied. Carries the environment-review result so it can still be shown."""

    def __init__(self, result: AnalysisResult):
        super().__init__(ENVIRONMENT_ONLY_MESSAGE, code="ENVIRONMENT_ONLY", hint=ENVIRONMENT_ONLY_HINT)
        self.result = result


def analyze_uploads(file: bytes | None, environment: bytes | None, file_name: str | None = None,
                    environment_name: str | None = None) -> AnalysisResult:
    """`file` is normally the collection and `environment` the optional environment; the roles are detected from
    the content, so files dropped in the wrong slot are still handled."""
    named = [(b, n) for b, n in ((file, file_name), (environment, environment_name)) if b is not None]
    docs = [load_document(b) for b, _ in named]
    names = [n for _, n in named]
    if not docs:
        raise ParseError("No file was uploaded.", code="NO_FILE", hint="Upload an API collection or a Postman environment.")
    colls = [d for d in docs if d.kind != "environment"]
    envs = [d for d in docs if d.kind == "environment"]
    if len(colls) > 1:
        raise ParseError("Two API collections were uploaded, but only one collection can be analyzed at a time.",
                         code="TWO_COLLECTIONS", hint="Upload one collection, plus an optional Postman environment file.")
    env = build_environment(envs[0]) if envs else None
    if not colls:
        raise EnvironmentOnlyError(analyze_environment_only(env))  # type: ignore[arg-type]
    result = analyze_collection(build_collection(colls[0], env), env)
    result.collection.file_name = names[docs.index(colls[0])]
    return result
