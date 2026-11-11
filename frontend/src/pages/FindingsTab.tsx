import { useMemo, useState } from "react";
import { Collapse } from "../components/motion";
import { Button, Card, ChevronIcon, EmptyState, KeyIcon, LayersIcon, MethodBadge, SearchIcon, SeverityChip, Tag } from "../components/ui";
import { SEVERITIES, type Endpoint, type Finding, type FindingGroup } from "../types";

interface Props {
  findings: Finding[];
  epMap: Map<string, Endpoint>;
  /** Used on the Endpoints tab: no toolbar, no group headers and no endpoint column. */
  compact?: boolean;
}

const GROUPS: { key: FindingGroup; title: string; blurb: string }[] = [
  { key: "Endpoint", title: "Endpoint findings", blurb: "Misconfigurations found in individual requests." },
  { key: "Collection", title: "Collection findings", blurb: "Issues that apply to the whole collection or API document." },
  { key: "Environment", title: "Environment findings", blurb: "Issues found in the Postman environment file (not tied to one endpoint)." },
];

function FindingCard({ f, epMap, open, onToggle, showEndpoint }: { f: Finding; epMap: Map<string, Endpoint>; open: boolean; onToggle: () => void; showEndpoint: boolean }) {
  const ep = f.endpoint_id ? epMap.get(f.endpoint_id) : undefined;
  return (
    <Card className="overflow-hidden">
      <button type="button" aria-expanded={open} onClick={onToggle} className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-[var(--row-hover)]">
        <ChevronIcon open={open} className="mt-1 h-4 w-4 shrink-0 text-faint" />
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center gap-2">
            <SeverityChip severity={f.severity} />
            <span className="font-medium">{f.issue}</span>
          </span>
          {showEndpoint && (
            <span className="mt-1.5 flex items-start gap-2 text-xs text-muted">
              {ep ? <><MethodBadge method={ep.method} /><span className="mono break-all">{ep.url}</span></> : <span>{f.group === "Environment" ? "Environment file" : "Collection-wide"}</span>}
            </span>
          )}
        </span>
        <span className="mono hidden shrink-0 text-xs text-faint sm:block">{f.id}</span>
      </button>
      <Collapse open={open}>
        <div className="space-y-3 border-t border-line px-4 py-4 text-sm sm:pl-11">
          <div>
            <h4 className="eyebrow mb-1.5">Evidence (masked)</h4>
            <pre className="codeblock">{f.evidence_masked}</pre>
          </div>
          <div className="callout callout-fix">
            <h4 className="eyebrow mb-1" style={{ color: "var(--accent)" }}>Remediation</h4>
            <p>{f.remediation}</p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-faint">Standards</span>
            {f.standard_refs.map((r) => <Tag key={r}>{r}</Tag>)}
          </div>
        </div>
      </Collapse>
    </Card>
  );
}

export default function FindingsTab({ findings, epMap, compact }: Props) {
  const [q, setQ] = useState("");
  const [sev, setSev] = useState("");
  const [group, setGroup] = useState("");
  const [open, setOpen] = useState<Set<string>>(new Set());

  const list = useMemo(() => {
    const s = q.trim().toLowerCase();
    return findings.filter((f) => {
      if (sev && f.severity !== sev) return false;
      if (group && f.group !== group) return false;
      if (!s) return true;
      const ep = f.endpoint_id ? epMap.get(f.endpoint_id) : undefined;
      return `${f.issue} ${f.evidence_masked} ${f.remediation} ${f.standard_refs.join(" ")} ${ep?.url ?? ""} ${ep?.name ?? ""}`.toLowerCase().includes(s);
    });
  }, [findings, q, sev, group, epMap]);

  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    for (const f of findings) c[f.group] = (c[f.group] ?? 0) + 1;
    return c;
  }, [findings]);

  const toggle = (id: string) => setOpen((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const allOpen = list.length > 0 && list.every((f) => open.has(f.id));

  if (findings.length === 0) {
    return <EmptyState art="clean" title="No static findings" hint="None of the built-in checks flagged this input. Run the generated test cases to look for runtime issues." />;
  }

  return (
    <div className="space-y-4">
      {!compact && (
        <Card className="flex flex-wrap items-center gap-2 p-3">
          <div className="relative min-w-[12rem] flex-1">
            <SearchIcon className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-faint" />
            <input type="search" aria-label="Search findings" className="input w-full !pl-8" placeholder="Search findings…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <select aria-label="Severity" className="input" value={sev} onChange={(e) => setSev(e.target.value)}>
            <option value="">Severity: all</option>
            {SEVERITIES.map((s) => <option key={s}>{s}</option>)}
          </select>
          <select aria-label="Group" className="input" value={group} onChange={(e) => setGroup(e.target.value)}>
            <option value="">Group: all</option>
            {GROUPS.filter((g) => counts[g.key]).map((g) => <option key={g.key} value={g.key}>{g.title} ({counts[g.key]})</option>)}
          </select>
          <Button size="sm" onClick={() => setOpen(allOpen ? new Set() : new Set(list.map((f) => f.id)))}>{allOpen ? "Collapse all" : "Expand all"}</Button>
          <span className="tnum text-sm text-muted" aria-live="polite">Showing <strong className="text-fg">{list.length}</strong> of <strong className="text-fg">{findings.length}</strong></span>
        </Card>
      )}

      {list.length === 0 ? (
        <EmptyState art="search" title="No findings match your search" hint="Try a different search term or severity."
          action={<Button onClick={() => { setQ(""); setSev(""); setGroup(""); }}>Clear filters</Button>} />
      ) : (
        GROUPS.map((g, gi) => {
          const items = list.filter((f) => f.group === g.key);
          if (!items.length) return null;
          return (
            <section key={g.key} aria-labelledby={`grp-${g.key}`} className="rise space-y-2" style={{ animationDelay: `${gi * 60}ms` }}>
              {!compact && (
                <div className="flex flex-wrap items-center gap-x-3 gap-y-0.5 pt-1">
                  <h3 id={`grp-${g.key}`} className="flex items-center gap-2 text-sm font-semibold">
                    {g.key === "Environment" ? <KeyIcon className="h-4 w-4 text-[var(--g3)]" /> : <LayersIcon className="h-4 w-4 text-[var(--g1)]" />}
                    {g.title}
                    <span className="tnum rounded-full border border-line bg-inset px-2 text-xs text-muted">{items.length}</span>
                  </h3>
                  <p className="text-xs text-muted">{g.blurb}</p>
                </div>
              )}
              <div className="space-y-2">
                {items.map((f) => (
                  <FindingCard key={f.id} f={f} epMap={epMap} open={open.has(f.id)} onToggle={() => toggle(f.id)} showEndpoint={!compact && g.key === "Endpoint"} />
                ))}
              </div>
            </section>
          );
        })
      )}
    </div>
  );
}
