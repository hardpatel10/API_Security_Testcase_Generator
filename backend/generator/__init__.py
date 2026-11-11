"""Test case generation + analysis orchestration."""
from __future__ import annotations

from collections import Counter

from ..models import (
    SEVERITIES, STATUSES, AnalysisResult, Collection, CollectionInfo, Endpoint, Environment, EnvironmentInfo, Notice,
    Summary, TestCase,
)
from ..rules import review_environment, run_rules
from ..standards import owasp_label
from .catalog import BUILDERS
from .traits import Traits, detect_traits

__all__ = ["generate_test_cases", "analyze_collection", "analyze_environment_only", "build_summary", "detect_traits", "Traits"]


def tests_for_endpoint(ep: Endpoint) -> list[dict]:
    t = detect_traits(ep)
    out: list[dict] = []
    for b in BUILDERS:
        out.extend(b(ep, t))
    return out


def generate_test_cases(endpoints: list[Endpoint]) -> list[TestCase]:
    cases: list[TestCase] = []
    n = 0
    for ep in endpoints:
        for d in tests_for_endpoint(ep):
            n += 1
            cases.append(TestCase(
                id=f"TC-{n:03d}", endpoint_id=ep.id, title=d["title"], description=d["description"],
                category=d["category"], how_to_test=d["how_to_test"], test_data=d["test_data"],
                expected_result=d["expected_result"], severity=d["severity"], owasp_api=owasp_label(d["api"]),
                cwe=d["cwe"], asvs=d["asvs"], wstg=d["wstg"],
            ))
    return cases


def build_summary(endpoints, findings, test_cases) -> Summary:
    def count(items, order=None):
        c = Counter(items)
        if order:
            return {k: c.get(k, 0) for k in order}
        return dict(sorted(c.items(), key=lambda kv: (-kv[1], kv[0])))

    return Summary(
        total_endpoints=len(endpoints), total_test_cases=len(test_cases), total_findings=len(findings),
        test_cases_by_severity=count([t.severity for t in test_cases], SEVERITIES),
        test_cases_by_category=count([t.category for t in test_cases]),
        test_cases_by_owasp=count([t.owasp_api for t in test_cases]),
        test_cases_by_status=count([t.status for t in test_cases], STATUSES),
        findings_by_severity=count([f.severity for f in findings], SEVERITIES),
        environment_findings=sum(1 for f in findings if f.group == "Environment"),
    )


def _env_info(env: Environment, applied: bool) -> EnvironmentInfo:
    return EnvironmentInfo(name=env.name, scope=env.scope, variable_count=sum(1 for v in env.variables if v.enabled),
                           applied=applied)


def _number(findings):
    for i, f in enumerate(findings, 1):
        f.id = f"F-{i:03d}"
    return findings


def analyze_collection(collection: Collection, environment: Environment | None = None) -> AnalysisResult:
    findings = run_rules(collection)
    if environment:
        findings += review_environment(environment)
    _number(findings)
    test_cases = generate_test_cases(collection.endpoints)
    return AnalysisResult(
        collection=CollectionInfo(name=collection.name, source_type=collection.source_type,
                                  base_url=collection.base_url, warnings=collection.warnings),
        endpoints=collection.endpoints, findings=findings, test_cases=test_cases,
        summary=build_summary(collection.endpoints, findings, test_cases),
        environment=_env_info(environment, True) if environment else None,
    )


ENVIRONMENT_ONLY_MESSAGE = "This is a Postman environment file, not a collection. It has variables but no requests."
ENVIRONMENT_ONLY_HINT = "In Postman, open the collection > ... > Export > Collection v2.1."


def analyze_environment_only(environment: Environment) -> AnalysisResult:
    """Environment-review mode: no requests, so only the environment rules run."""
    findings = _number(review_environment(environment))
    return AnalysisResult(
        collection=CollectionInfo(name=environment.name, source_type="environment"),
        endpoints=[], findings=findings, test_cases=[], summary=build_summary([], findings, []),
        environment=_env_info(environment, False),
        notice=Notice(code="ENVIRONMENT_ONLY", message=ENVIRONMENT_ONLY_MESSAGE, hint=ENVIRONMENT_ONLY_HINT),
    )
