import type { Endpoint, Filters, TestCase } from "../types";

const SEV_ORDER: Record<string, number> = { High: 0, Medium: 1, Low: 2, Info: 3 };

export function filtersActive(f: Filters): boolean {
  return !!(f.search || f.severity || f.owasp || f.method || f.status || f.endpoint);
}

export function applyFilters(cases: TestCase[], endpoints: Map<string, Endpoint>, f: Filters): TestCase[] {
  const q = f.search.trim().toLowerCase();
  const out = cases.filter((t) => {
    const ep = endpoints.get(t.endpoint_id);
    if (f.severity && t.severity !== f.severity) return false;
    if (f.owasp && t.owasp_api !== f.owasp) return false;
    if (f.status && t.status !== f.status) return false;
    if (f.endpoint && t.endpoint_id !== f.endpoint) return false;
    if (f.method && ep?.method !== f.method) return false;
    if (q) {
      const hay = `${t.id} ${t.title} ${t.category} ${t.owasp_api} ${t.cwe.join(" ")} ${t.asvs.join(" ")} ${t.notes} ${ep?.url ?? ""} ${ep?.name ?? ""} ${ep?.method ?? ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
  const byId = (a: TestCase, b: TestCase) => a.id.localeCompare(b.id);
  const bySev = (a: TestCase, b: TestCase) => SEV_ORDER[a.severity] - SEV_ORDER[b.severity] || byId(a, b);
  const secondary = f.sort === "severity" ? bySev : byId;
  return [...out].sort((a, b) => {
    if (f.group || f.sort === "endpoint") {
      const e = a.endpoint_id.localeCompare(b.endpoint_id);
      if (e) return e;
    }
    return secondary(a, b);
  });
}

export function stepsText(t: TestCase): string {
  return `${t.id} - ${t.title}\n` + t.how_to_test.map((s, i) => `${i + 1}. ${s}`).join("\n");
}
