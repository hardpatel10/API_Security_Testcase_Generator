from __future__ import annotations

from ..models import Collection, Finding
from .base import Rule
from .environment import review_environment
from .rules import ALL_RULES, id_path_params, literal_id_segments

__all__ = ["Rule", "review_environment", "ALL_RULES", "run_rules", "id_path_params", "literal_id_segments"]

_SEV_ORDER = {"High": 0, "Medium": 1, "Low": 2, "Info": 3}


def run_rules(collection: Collection, rules: list[Rule] | None = None) -> list[Finding]:
    """Run all rules; collection-wide findings first, then per endpoint. Assigns F-### ids."""
    rules = rules if rules is not None else ALL_RULES
    findings: list[Finding] = []
    for r in rules:
        findings.extend(r.match_collection(collection))
    for ep in collection.endpoints:
        for r in rules:
            f = r.match(ep)
            if f:
                findings.append(f)
    for i, f in enumerate(findings, 1):
        f.id = f"F-{i:03d}"
    return findings
