"""Shared data models used by the parsers, rules, generator, API and Excel export."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["High", "Medium", "Low", "Info"]
Status = Literal["Not Started", "Pass", "Fail", "N/A"]

SEVERITIES: list[str] = ["High", "Medium", "Low", "Info"]
STATUSES: list[str] = ["Not Started", "Pass", "Fail", "N/A"]

SAFETY_NOTE = "Perform tests only on systems you are authorized to assess."
CREDIT_NAME = "Hard Pansara"
CREDIT_URL = "https://www.linkedin.com/in/hard-pansara-22582a288/"


class SecretRef(BaseModel):
    """A hard-coded secret found in the collection. Only the masked value is ever stored."""

    location: str  # header | query | body | variable | auth
    name: str
    masked: str


class Endpoint(BaseModel):
    id: str
    name: str
    method: str
    url: str
    path_params: list[str] = Field(default_factory=list)
    query_params: list[str] = Field(default_factory=list)
    headers: dict[str, str] = Field(default_factory=dict)  # secret values already masked
    body_fields: list[str] = Field(default_factory=list)
    auth_type: str = "none"  # none | basic | bearer | apikey-header | apikey-query | apikey-cookie | oauth2 | other
    folder: str = ""
    # Extra traits used by rules / generator
    body_content_type: Optional[str] = None
    has_file_upload: bool = False
    responses: list[str] = Field(default_factory=list)  # documented status codes (OpenAPI only)
    source: str = "postman"  # postman | openapi
    secrets: list[SecretRef] = Field(default_factory=list)


class Collection(BaseModel):
    name: str
    source_type: str  # postman | openapi | swagger
    base_url: str = ""
    endpoints: list[Endpoint] = Field(default_factory=list)
    variable_secrets: list[SecretRef] = Field(default_factory=list)
    has_security_schemes: Optional[bool] = None  # OpenAPI only; None = not applicable
    warnings: list[str] = Field(default_factory=list)


class EnvVar(BaseModel):
    """A Postman environment/globals variable. Raw values stay in memory only and are never serialized to the API."""

    key: str
    value: str = ""
    type: str = "default"  # default | secret | any
    enabled: bool = True


class Environment(BaseModel):
    name: str
    scope: str = "environment"  # environment | globals
    variables: list[EnvVar] = Field(default_factory=list)


class EnvironmentInfo(BaseModel):
    name: str
    scope: str = "environment"
    variable_count: int = 0
    applied: bool = False  # True when used to resolve {{variables}} in a collection


class Notice(BaseModel):
    code: str
    message: str
    hint: str = ""


class TestCase(BaseModel):
    __test__ = False  # not a pytest class

    id: str
    endpoint_id: str
    title: str
    description: str
    category: str
    how_to_test: list[str]
    test_data: str
    expected_result: str
    severity: Severity
    owasp_api: str  # e.g. "API1:2023 Broken Object Level Authorization"
    cwe: list[str] = Field(default_factory=list)
    asvs: list[str] = Field(default_factory=list)
    wstg: list[str] = Field(default_factory=list)
    status: Status = "Not Started"
    notes: str = ""


class Finding(BaseModel):
    id: str
    endpoint_id: Optional[str] = None  # None for collection-wide and environment findings
    group: str = "Endpoint"  # Endpoint | Collection | Environment
    issue: str
    evidence_masked: str
    severity: Severity
    standard_refs: list[str] = Field(default_factory=list)
    remediation: str


class CollectionInfo(BaseModel):
    name: str
    source_type: str
    base_url: str = ""
    file_name: Optional[str] = None  # uploaded file name (shown on the Excel cover sheet)
    warnings: list[str] = Field(default_factory=list)


class Summary(BaseModel):
    total_endpoints: int = 0
    total_test_cases: int = 0
    total_findings: int = 0
    test_cases_by_severity: dict[str, int] = Field(default_factory=dict)
    test_cases_by_category: dict[str, int] = Field(default_factory=dict)
    test_cases_by_owasp: dict[str, int] = Field(default_factory=dict)
    test_cases_by_status: dict[str, int] = Field(default_factory=dict)
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    environment_findings: int = 0


class AnalysisResult(BaseModel):
    collection: CollectionInfo
    endpoints: list[Endpoint]
    findings: list[Finding]
    test_cases: list[TestCase]
    summary: Summary
    environment: Optional[EnvironmentInfo] = None
    notice: Optional[Notice] = None


class ExportRequest(BaseModel):
    analysis: AnalysisResult
    test_case_ids: Optional[list[str]] = None  # None = export all
