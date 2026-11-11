"""Static misconfiguration rules. Each rule is a small class: match(endpoint) -> Finding | None."""
from __future__ import annotations

import re

from ..models import Collection, Endpoint, Finding
from ..parsers.common import path_of

STATE_CHANGING = {"PUT", "PATCH", "DELETE"}
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
PUBLIC_FLOW_RE = re.compile(
    r"(login|signin|sign-in|signup|sign-up|register|authenticate|oauth|token|password|forgot|reset|otp|verify|"
    r"health|status|ping|version|docs|openapi|swagger)", re.I)


class Rule:
    """Base class. Override match() for per-endpoint rules or match_collection() for collection-wide ones."""

    id = "RULE"
    title = ""

    def match(self, endpoint: Endpoint) -> Finding | None:  # pragma: no cover - default
        return None

    def match_collection(self, collection: Collection) -> list[Finding]:
        return []

    def finding(self, endpoint_id: str | None, issue: str, evidence: str, severity: str,
                refs: list[str], remediation: str) -> Finding:
        return Finding(id="", endpoint_id=endpoint_id, group="Endpoint" if endpoint_id else "Collection", issue=issue, evidence_masked=evidence,
                       severity=severity, standard_refs=refs, remediation=remediation)  # type: ignore[arg-type]


def endpoint_path(ep: Endpoint) -> str:
    return path_of(ep.url)


def path_segments(ep: Endpoint) -> list[str]:
    return [s for s in endpoint_path(ep).split("/") if s]


def is_public_flow(ep: Endpoint) -> bool:
    """Login / registration / health style endpoints are commonly intentionally unauthenticated."""
    return bool(PUBLIC_FLOW_RE.search(endpoint_path(ep)))
