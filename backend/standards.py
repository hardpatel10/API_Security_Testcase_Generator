"""Security standards catalog: OWASP API Top 10 (2023), OWASP ASVS 4.0, CWE and OWASP WSTG.

Every reference used by rules or the test generator must exist here (enforced by unit tests), so the
UI "Standards" tab and the Excel "Standards Reference" sheet are always complete.
"""
from __future__ import annotations

OWASP_API: dict[str, tuple[str, str]] = {
    "API1": ("Broken Object Level Authorization",
             "APIs expose object identifiers; missing per-object authorization lets users access others' data."),
    "API2": ("Broken Authentication",
             "Weak or missing authentication mechanisms let attackers assume other users' identities."),
    "API3": ("Broken Object Property Level Authorization",
             "Missing authorization at property level causes excessive data exposure or mass assignment."),
    "API4": ("Unrestricted Resource Consumption",
             "Requests consume CPU, memory, bandwidth or paid services without limits, enabling DoS or cost abuse."),
    "API5": ("Broken Function Level Authorization",
             "Users can call administrative or privileged functions they should not have access to."),
    "API6": ("Unrestricted Access to Sensitive Business Flows",
             "Business flows (sign-up, purchase, reset) can be abused through automation at scale."),
    "API7": ("Server Side Request Forgery",
             "The API fetches a user-supplied URL without validation, reaching internal or unintended resources."),
    "API8": ("Security Misconfiguration",
             "Missing hardening, permissive CORS, verbose errors, missing TLS/headers, or unsafe defaults."),
    "API9": ("Improper Inventory Management",
             "Undocumented, debug, old or internal endpoints and versions remain exposed."),
    "API10": ("Unsafe Consumption of APIs",
              "Weak validation of data processed by the API (injection, malformed or untrusted input)."),
}


def owasp_label(key: str) -> str:
    """'API1' -> 'API1:2023 Broken Object Level Authorization'."""
    return f"{key}:2023 {OWASP_API[key][0]}"


OWASP_API_LABELS: list[str] = [owasp_label(k) for k in OWASP_API]
OWASP_API_URLS: dict[str, str] = {
    "API1": "0xa1-broken-object-level-authorization", "API2": "0xa2-broken-authentication",
    "API3": "0xa3-broken-object-property-level-authorization", "API4": "0xa4-unrestricted-resource-consumption",
    "API5": "0xa5-broken-function-level-authorization",
    "API6": "0xa6-unrestricted-access-to-sensitive-business-flows",
    "API7": "0xa7-server-side-request-forgery", "API8": "0xa8-security-misconfiguration",
    "API9": "0xa9-improper-inventory-management", "API10": "0xaa-unsafe-consumption-of-apis",
}

# OWASP ASVS 4.0.3 requirement IDs -> short description
ASVS: dict[str, str] = {
    "V2.1.1": "Passwords are at least 12 characters (credential policy).",
    "V2.2.1": "Anti-automation controls mitigate credential stuffing, brute force and lockout abuse.",
    "V2.5.6": "Forgotten-password and credential recovery uses a secure mechanism.",
    "V2.8.1": "Time-based OTPs have a defined lifetime and cannot be reused.",
    "V2.10.4": "Secrets and API keys are managed securely and not stored in source code.",
    "V3.5.2": "Session tokens are used rather than static API secrets and keys.",
    "V3.5.3": "Stateless tokens are protected against tampering, replay and null-cipher attacks.",
    "V4.1.1": "Access control is enforced on a trusted service layer.",
    "V4.1.2": "User/data attributes used by access control cannot be manipulated by end users.",
    "V4.1.3": "Principle of least privilege is applied to functions and data.",
    "V4.2.1": "Sensitive data and APIs are protected against IDOR on create, read, update and delete.",
    "V4.3.1": "Administrative interfaces use appropriate multi-factor authentication.",
    "V5.1.3": "All input is validated using positive (allow-list) validation.",
    "V5.1.4": "Structured data is strongly typed and validated against a schema.",
    "V5.1.5": "URL redirects and forwards only go to allow-listed destinations.",
    "V5.2.6": "Server-side requests to untrusted URLs are protected against SSRF.",
    "V5.3.3": "Context-aware output encoding prevents XSS.",
    "V5.3.4": "Database queries (SQL/NoSQL) are parameterized or otherwise protected from injection.",
    "V7.4.1": "A generic message is shown for unexpected or security-sensitive errors.",
    "V8.3.1": "Sensitive data is sent in the body/headers, never in the URL query string.",
    "V9.1.1": "Secured TLS is used for all client connectivity with no fallback to plaintext.",
    "V11.1.4": "Anti-automation controls protect against excessive calls and abuse of business flows.",
    "V12.1.1": "Large files that could exhaust storage or cause DoS are not accepted.",
    "V12.2.1": "Files from untrusted sources are validated to be of the expected type.",
    "V13.1.3": "API URLs do not expose sensitive information such as API keys or session tokens.",
    "V13.1.4": "Authorization decisions are made at both the URI and the resource level.",
    "V13.1.5": "Requests with unexpected or missing content types are rejected.",
    "V13.2.1": "Enabled RESTful HTTP methods are a valid choice for the user and action.",
    "V13.2.2": "JSON schema validation is applied to request bodies.",
    "V14.3.2": "Debug modes and verbose diagnostics are disabled in production.",
    "V14.4.4": "Responses contain X-Content-Type-Options: nosniff.",
    "V14.4.5": "Strict-Transport-Security is set on all responses.",
    "V14.5.1": "The server only accepts the HTTP methods in use, including pre-flight OPTIONS.",
    "V14.5.3": "CORS uses a strict allow-list of trusted origins and does not accept 'null'.",
}

CWE: dict[str, str] = {
    "CWE-16": "Configuration",
    "CWE-20": "Improper Input Validation",
    "CWE-79": "Cross-site Scripting (XSS)",
    "CWE-89": "SQL Injection",
    "CWE-200": "Exposure of Sensitive Information to an Unauthorized Actor",
    "CWE-209": "Error Message Containing Sensitive Information",
    "CWE-213": "Exposure of Sensitive Information Due to Incompatible Policies",
    "CWE-284": "Improper Access Control",
    "CWE-285": "Improper Authorization",
    "CWE-287": "Improper Authentication",
    "CWE-306": "Missing Authentication for Critical Function",
    "CWE-307": "Improper Restriction of Excessive Authentication Attempts",
    "CWE-319": "Cleartext Transmission of Sensitive Information",
    "CWE-347": "Improper Verification of Cryptographic Signature",
    "CWE-400": "Uncontrolled Resource Consumption",
    "CWE-434": "Unrestricted Upload of File with Dangerous Type",
    "CWE-489": "Active Debug Code",
    "CWE-598": "Use of GET Request Method With Sensitive Query Strings",
    "CWE-601": "URL Redirection to Untrusted Site (Open Redirect)",
    "CWE-613": "Insufficient Session Expiration",
    "CWE-639": "Authorization Bypass Through User-Controlled Key",
    "CWE-650": "Trusting HTTP Permission Methods on the Server Side",
    "CWE-693": "Protection Mechanism Failure",
    "CWE-770": "Allocation of Resources Without Limits or Throttling",
    "CWE-798": "Use of Hard-coded Credentials",
    "CWE-799": "Improper Control of Interaction Frequency",
    "CWE-862": "Missing Authorization",
    "CWE-915": "Improperly Controlled Modification of Dynamically-Determined Object Attributes",
    "CWE-918": "Server-Side Request Forgery (SSRF)",
    "CWE-942": "Permissive Cross-domain Policy with Untrusted Domains",
    "CWE-943": "Improper Neutralization of Special Elements in Data Query Logic (NoSQL Injection)",
    "CWE-1284": "Improper Validation of Specified Quantity in Input",
    "CWE-204": "Observable Response Discrepancy",
    "CWE-522": "Insufficiently Protected Credentials",
}

WSTG: dict[str, str] = {
    "WSTG-ATHN-01": "Testing for credentials transported over an encrypted channel",
    "WSTG-ATHN-03": "Testing for weak lock out mechanism",
    "WSTG-ATHN-04": "Testing for bypassing authentication schema",
    "WSTG-ATHN-09": "Testing for weak password change or reset functionalities",
    "WSTG-ATHZ-02": "Testing for bypassing authorization schema",
    "WSTG-ATHZ-03": "Testing for privilege escalation",
    "WSTG-ATHZ-04": "Testing for insecure direct object references",
    "WSTG-BUSL-05": "Test number of times a function can be used limits",
    "WSTG-BUSL-08": "Test upload of unexpected file types",
    "WSTG-BUSL-09": "Test upload of malicious files",
    "WSTG-BUSL-01": "Test business logic data validation",
    "WSTG-CLNT-04": "Testing for client-side URL redirect",
    "WSTG-CLNT-07": "Testing cross origin resource sharing",
    "WSTG-CONF-05": "Enumerate infrastructure and application admin interfaces",
    "WSTG-CONF-06": "Test HTTP methods",
    "WSTG-CONF-07": "Test HTTP Strict Transport Security",
    "WSTG-CONF-14": "Test other HTTP security header misconfigurations",
    "WSTG-CRYP-01": "Testing for weak transport layer security",
    "WSTG-ERRH-01": "Testing for improper error handling",
    "WSTG-IDNT-04": "Testing for account enumeration and guessable user account",
    "WSTG-INFO-06": "Identify application entry points",
    "WSTG-INPV-01": "Testing for reflected cross site scripting",
    "WSTG-INPV-02": "Testing for stored cross site scripting",
    "WSTG-INPV-05": "Testing for SQL injection (incl. NoSQL injection)",
    "WSTG-INPV-19": "Testing for server-side request forgery",
    "WSTG-INPV-20": "Testing for mass assignment",
    "WSTG-SESS-10": "Testing JSON web tokens",
}

STANDARD_LINKS = {
    "owasp_api": "https://owasp.org/API-Security/editions/2023/en/{slug}/",
    "asvs": "https://owasp.org/www-project-application-security-verification-standard/",
    "cwe": "https://cwe.mitre.org/data/definitions/{num}.html",
    "wstg": "https://owasp.org/www-project-web-security-testing-guide/latest/",
}

STANDARDS_SUMMARY: list[tuple[str, str]] = [
    ("OWASP API Security Top 10 (2023)",
     "The ten most critical API security risks; used to categorize every test case and finding."),
    ("OWASP ASVS 4.0",
     "Application Security Verification Standard: a requirement checklist to verify technical security controls."),
    ("CWE",
     "Common Weakness Enumeration: a community catalog of software weakness types, used for precise classification."),
    ("OWASP WSTG",
     "Web Security Testing Guide: step-by-step testing procedures that explain how to test each weakness."),
]


def asvs_label(rid: str) -> str:
    return f"ASVS {rid}"
