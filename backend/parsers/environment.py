"""Postman environment / globals export parser."""
from __future__ import annotations

from typing import Any

from ..models import Environment, EnvVar
from .common import ParseError, resolution_value

ENV_SCOPES = ("environment", "globals")


def is_environment(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if isinstance(data.get("info"), dict) and "item" in data:
        return False  # a collection
    return isinstance(data.get("values"), list) or data.get("_postman_variable_scope") in ENV_SCOPES


def parse_environment(data: dict) -> Environment:
    values = data.get("values", [])
    if not isinstance(values, list):
        raise ParseError("Invalid Postman environment: 'values' must be a list.", code="INVALID_FORMAT",
                         hint="Re-export the environment from Postman (Environments > ... > Export).")
    variables: list[EnvVar] = []
    for v in values:
        if not isinstance(v, dict) or not v.get("key"):
            continue
        raw = v.get("value")
        variables.append(EnvVar(
            key=str(v["key"]), value="" if raw is None or isinstance(raw, (dict, list)) else str(raw),
            type=str(v.get("type") or "default").lower(), enabled=v.get("enabled", True) is not False,
        ))
    scope = data.get("_postman_variable_scope")
    return Environment(name=str(data.get("name") or "Environment"),
                       scope=scope if scope in ENV_SCOPES else "environment", variables=variables)


def resolution_variables(env: Environment | None) -> dict[str, str]:
    """{{name}} -> substitution value. Placeholders are skipped; secrets are substituted masked."""
    out: dict[str, str] = {}
    if env:
        for v in env.variables:
            if v.enabled:
                rv = resolution_value(v.key, v.value)
                if rv is not None:
                    out[v.key] = rv
    return out
