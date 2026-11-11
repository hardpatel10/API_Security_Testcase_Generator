export type Severity = "High" | "Medium" | "Low" | "Info";
export type Status = "Not Started" | "Pass" | "Fail" | "N/A";

export const SEVERITIES: Severity[] = ["High", "Medium", "Low", "Info"];
export const STATUSES: Status[] = ["Not Started", "Pass", "Fail", "N/A"];

export interface Endpoint {
  id: string;
  name: string;
  method: string;
  url: string;
  path_params: string[];
  query_params: string[];
  headers: Record<string, string>;
  body_fields: string[];
  auth_type: string;
  folder: string;
  body_content_type: string | null;
  has_file_upload: boolean;
  responses: string[];
  source: string;
  secrets: { location: string; name: string; masked: string }[];
}

export interface TestCase {
  id: string;
  endpoint_id: string;
  title: string;
  description: string;
  category: string;
  how_to_test: string[];
  test_data: string;
  expected_result: string;
  severity: Severity;
  owasp_api: string;
  cwe: string[];
  asvs: string[];
  wstg: string[];
  status: Status;
  notes: string;
}

export type FindingGroup = "Endpoint" | "Collection" | "Environment";

export interface Finding {
  id: string;
  endpoint_id: string | null; // null for collection-wide and environment findings
  group: FindingGroup;
  issue: string;
  evidence_masked: string;
  severity: Severity;
  standard_refs: string[];
  remediation: string;
}

export interface Summary {
  total_endpoints: number;
  total_test_cases: number;
  total_findings: number;
  test_cases_by_severity: Record<string, number>;
  test_cases_by_category: Record<string, number>;
  test_cases_by_owasp: Record<string, number>;
  test_cases_by_status: Record<string, number>;
  findings_by_severity: Record<string, number>;
  environment_findings: number;
}

export interface Notice {
  code: string;
  message: string;
  hint: string;
}

export interface Analysis {
  collection: { name: string; source_type: string; base_url: string; warnings: string[]; file_name?: string | null };
  endpoints: Endpoint[];
  findings: Finding[];
  test_cases: TestCase[];
  summary: Summary;
  environment?: { name: string; scope: string; variable_count: number; applied: boolean } | null;
  notice?: Notice | null;
}

/** User-editable state kept separately from the (immutable) analysis. */
export type Progress = Record<string, { status: Status; notes: string }>;

export type SortKey = "id" | "severity" | "endpoint";

export interface Filters {
  search: string;
  severity: string;
  owasp: string;
  method: string;
  status: string;
  endpoint: string;
  sort: SortKey;
  group: boolean;
}

export const DEFAULT_FILTERS: Filters = {
  search: "", severity: "", owasp: "", method: "", status: "", endpoint: "", sort: "id", group: false,
};

export const SAFETY_NOTE = "Perform tests only on systems you are authorized to assess.";
