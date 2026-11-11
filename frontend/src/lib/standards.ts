export interface OwaspInfo {
  key: string;
  name: string;
  slug: string;
  desc: string;
}

export const OWASP_API: OwaspInfo[] = [
  { key: "API1", name: "Broken Object Level Authorization", slug: "0xa1-broken-object-level-authorization", desc: "Object identifiers are exposed and per-object authorization is missing." },
  { key: "API2", name: "Broken Authentication", slug: "0xa2-broken-authentication", desc: "Weak or missing authentication lets attackers assume other identities." },
  { key: "API3", name: "Broken Object Property Level Authorization", slug: "0xa3-broken-object-property-level-authorization", desc: "Excessive data exposure and mass assignment of object properties." },
  { key: "API4", name: "Unrestricted Resource Consumption", slug: "0xa4-unrestricted-resource-consumption", desc: "Missing limits enable denial of service and cost abuse." },
  { key: "API5", name: "Broken Function Level Authorization", slug: "0xa5-broken-function-level-authorization", desc: "Privileged functions are reachable by users without the right role." },
  { key: "API6", name: "Unrestricted Access to Sensitive Business Flows", slug: "0xa6-unrestricted-access-to-sensitive-business-flows", desc: "Business flows can be automated and abused at scale." },
  { key: "API7", name: "Server Side Request Forgery", slug: "0xa7-server-side-request-forgery", desc: "The API fetches attacker-supplied URLs without validation." },
  { key: "API8", name: "Security Misconfiguration", slug: "0xa8-security-misconfiguration", desc: "Missing hardening, permissive CORS, verbose errors, weak TLS." },
  { key: "API9", name: "Improper Inventory Management", slug: "0xa9-improper-inventory-management", desc: "Debug, internal, old or undocumented endpoints remain exposed." },
  { key: "API10", name: "Unsafe Consumption of APIs", slug: "0xaa-unsafe-consumption-of-apis", desc: "Weak validation of untrusted input (injection, malformed data)." },
];

export const owaspKey = (label: string) => label.split(":")[0];

export const owaspUrl = (label: string) => {
  const info = OWASP_API.find((o) => o.key === owaspKey(label));
  return info ? `https://owasp.org/API-Security/editions/2023/en/${info.slug}/` : "https://owasp.org/API-Security/";
};
export const cweUrl = (id: string) => `https://cwe.mitre.org/data/definitions/${id.replace(/\D/g, "")}.html`;
export const ASVS_URL = "https://owasp.org/www-project-application-security-verification-standard/";
export const WSTG_URL = "https://owasp.org/www-project-web-security-testing-guide/latest/";

export const STANDARD_BLURBS = [
  {
    name: "OWASP API Security Top 10 (2023)",
    text: "The ten most critical API security risks. Every test case and finding is categorized against it so results can be prioritized.",
    url: "https://owasp.org/API-Security/editions/2023/en/0x00-header/",
  },
  {
    name: "OWASP ASVS 4.0",
    text: "The Application Security Verification Standard: a requirement checklist used to verify that technical security controls are implemented.",
    url: ASVS_URL,
  },
  {
    name: "CWE",
    text: "Common Weakness Enumeration: a community catalog of software weakness types that gives each issue a precise, tool-friendly identifier.",
    url: "https://cwe.mitre.org/",
  },
  {
    name: "OWASP WSTG",
    text: "The Web Security Testing Guide: detailed, step-by-step testing procedures that explain how to verify each weakness.",
    url: WSTG_URL,
  },
];
