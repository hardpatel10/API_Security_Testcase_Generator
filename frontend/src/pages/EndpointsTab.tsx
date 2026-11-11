import { useMemo, useState } from "react";
import { TestCaseCard } from "../components/TestCaseDetails";
import Tabs from "../components/Tabs";
import { Button, Card, EmptyState, MethodBadge, SearchIcon, Tag } from "../components/ui";
import type { Endpoint, Finding, Status, TestCase } from "../types";
import FindingsTab from "./FindingsTab";

interface Props {
  endpoints: Endpoint[];
  epMap: Map<string, Endpoint>;
  cases: TestCase[];
  findings: Finding[];
  setStatus: (ids: string[], s: Status) => void;
  setNotes: (id: string, notes: string) => void;
  onNewUpload: () => void;
  selId: string;
  setSelId: (id: string) => void;
}

const SUBTABS = ["Test Cases", "Findings"] as const;
type Sub = (typeof SUBTABS)[number];

export default function EndpointsTab({ endpoints, epMap, cases, findings, setStatus, setNotes, onNewUpload, selId, setSelId }: Props) {
  const [q, setQ] = useState("");
  const [sub, setSub] = useState<Sub>("Test Cases");

  const counts = useMemo(() => {
    const t = new Map<string, number>();
    const f = new Map<string, number>();
    for (const c of cases) t.set(c.endpoint_id, (t.get(c.endpoint_id) ?? 0) + 1);
    for (const x of findings) if (x.endpoint_id) f.set(x.endpoint_id, (f.get(x.endpoint_id) ?? 0) + 1);
    return { t, f };
  }, [cases, findings]);

  const list = useMemo(() => {
    const s = q.trim().toLowerCase();
    return s ? endpoints.filter((e) => `${e.id} ${e.name} ${e.method} ${e.url} ${e.folder}`.toLowerCase().includes(s)) : endpoints;
  }, [endpoints, q]);

  const ep = epMap.get(selId) ?? endpoints[0];
  const epCases = useMemo(() => cases.filter((c) => c.endpoint_id === ep?.id), [cases, ep]);
  const epFindings = useMemo(() => findings.filter((f) => f.endpoint_id === ep?.id), [findings, ep]);

  if (!ep) {
    return (
      <EmptyState art="upload" title="No endpoints to show" hint="Endpoints come from the requests in an API collection."
        action={<Button variant="primary" onClick={onNewUpload}>Upload a collection</Button>} />
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[21rem_1fr]">
      <div className="lg:sticky lg:top-[7rem] lg:self-start">
      <Card className="rise flex max-h-72 flex-col overflow-hidden lg:max-h-[calc(100vh-9.5rem)]">
        <div className="border-b border-line p-3">
          <div className="relative">
            <SearchIcon className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-faint" />
            <input type="search" aria-label="Search endpoints" className="input w-full !pl-8" placeholder="Search endpoints…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <p className="tnum mt-1.5 text-xs text-muted">{list.length} of {endpoints.length} endpoints</p>
        </div>
        <ul className="flex-1 overflow-y-auto p-1.5" role="listbox" aria-label="Endpoints">
          {list.length === 0 && <li className="flex items-center gap-2 p-4 text-sm text-muted"><SearchIcon className="h-4 w-4" /> No endpoints match your search.</li>}
          {list.map((e) => {
            const selected = e.id === ep.id;
            const nf = counts.f.get(e.id) ?? 0;
            return (
              <li key={e.id} role="option" aria-selected={selected}>
                <button
                  type="button"
                  onClick={() => setSelId(e.id)}
                  className={`flex w-full items-start gap-2.5 rounded-lg border-l-[3px] px-2.5 py-2.5 text-left transition-colors hover:bg-[var(--row-hover)] ${
                    selected ? "border-[var(--g1)] bg-[var(--row-hover)] shadow-[0_0_22px_-8px_var(--glow)]" : "border-transparent"
                  }`}
                >
                  <MethodBadge method={e.method} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-medium">{e.name}</span>
                    <span className="mono block truncate text-[11px] text-muted">{e.url.replace(/^https?:\/\/[^/]+/, "")}</span>
                  </span>
                  <span className="flex shrink-0 flex-col items-end gap-1 text-[11px]">
                    <span title="Test cases" className="tnum text-muted">{counts.t.get(e.id) ?? 0} tests</span>
                    {nf > 0 && <span title="Findings" className="chip sev-high !px-1.5 !py-0 !text-[11px]"><span className="dot" />{nf}</span>}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </Card>
      </div>

      <section className="min-w-0 space-y-3">
        <Card className="rise p-4 sm:p-5">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="mono text-xs text-faint">{ep.id}</span>
            <MethodBadge method={ep.method} />
            <h2 className="text-lg font-semibold">{ep.name}</h2>
          </div>
          <p className="mono mt-1.5 break-all text-[13px] text-muted">{ep.url}</p>
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm sm:grid-cols-4">
            <div><dt className="eyebrow">Auth</dt><dd className="mt-0.5"><Tag>{ep.auth_type}</Tag></dd></div>
            <div><dt className="eyebrow">Folder / tag</dt><dd className="mt-0.5">{ep.folder || "—"}</dd></div>
            <div><dt className="eyebrow">Path / query params</dt><dd className="mono mt-0.5 break-words text-xs">{[...ep.path_params, ...ep.query_params].join(", ") || "—"}</dd></div>
            <div><dt className="eyebrow">Body fields</dt><dd className="mono mt-0.5 break-words text-xs">{ep.body_fields.slice(0, 8).join(", ") || "—"}{ep.body_fields.length > 8 ? " …" : ""}</dd></div>
          </dl>
        </Card>

        <div className="flex">
          <Tabs tabs={SUBTABS} value={sub} onChange={setSub} label="Endpoint details" counts={{ "Test Cases": epCases.length, Findings: epFindings.length }} />
        </div>

        <div key={`${ep.id}-${sub}`} className="rise">
          {sub === "Test Cases" ? (
            epCases.length === 0 ? <EmptyState art="search" title="No test cases for this endpoint" /> : (
              <div className="space-y-2">
                {epCases.map((t) => <TestCaseCard key={t.id} tc={t} endpoint={ep} onStatus={setStatus} onNotes={setNotes} />)}
              </div>
            )
          ) : epFindings.length === 0 ? (
            <EmptyState art="clean" title="No static findings for this endpoint" hint="None of the built-in checks flagged this endpoint." />
          ) : (
            <FindingsTab findings={epFindings} epMap={epMap} compact />
          )}
        </div>
      </section>
    </div>
  );
}
