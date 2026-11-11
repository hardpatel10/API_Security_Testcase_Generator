import { useMemo, type CSSProperties, type ReactNode } from "react";
import { Card, ExternalIcon, EyeOffIcon, FileIcon, KeyIcon, LayersIcon, LockIcon, SearchIcon, ShieldIcon, TerminalIcon, AlertIcon, Tag } from "../components/ui";
import { ASVS_URL, cweUrl, OWASP_API, owaspKey, owaspUrl, STANDARD_BLURBS, WSTG_URL } from "../lib/standards";
import type { TestCase } from "../types";

const ICONS: Record<string, ReactNode> = {
  API1: <KeyIcon />, API2: <LockIcon />, API3: <EyeOffIcon />, API4: <LayersIcon />, API5: <ShieldIcon />,
  API6: <TerminalIcon />, API7: <SearchIcon />, API8: <AlertIcon />, API9: <FileIcon />, API10: <TerminalIcon />,
};
const stagger = (i: number): CSSProperties => ({ animationDelay: `${i * 45}ms` });

function topCounts(items: string[], n = 8): [string, number][] {
  const m = new Map<string, number>();
  for (const i of items) m.set(i, (m.get(i) ?? 0) + 1);
  return [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, n);
}

function TopList({ title, rows, href }: { title: string; rows: [string, number][]; href: (id: string) => string }) {
  return (
    <Card className="rise p-4">
      <h3 className="eyebrow mb-3">{title}</h3>
      <ul className="space-y-1.5 text-sm">
        {rows.map(([id, n]) => <li key={id} className="flex items-center justify-between"><Tag href={href(id)}>{id}</Tag><span className="tnum text-muted">{n}</span></li>)}
      </ul>
    </Card>
  );
}

export default function StandardsTab({ cases }: { cases: TestCase[] }) {
  const counts = useMemo(() => {
    const m = new Map<string, number>();
    for (const c of cases) m.set(owaspKey(c.owasp_api), (m.get(owaspKey(c.owasp_api)) ?? 0) + 1);
    return m;
  }, [cases]);
  const max = Math.max(1, ...counts.values());
  const cwe = useMemo(() => topCounts(cases.flatMap((c) => c.cwe)), [cases]);
  const asvs = useMemo(() => topCounts(cases.flatMap((c) => c.asvs)), [cases]);
  const wstg = useMemo(() => topCounts(cases.flatMap((c) => c.wstg)), [cases]);

  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {STANDARD_BLURBS.map((b, i) => (
          <a key={b.name} href={b.url} target="_blank" rel="noopener noreferrer" className="card card-hover rise block p-4" style={stagger(i)}>
            <h3 className="flex items-center justify-between gap-2 font-semibold">{b.name}<ExternalIcon className="h-3.5 w-3.5 text-faint" /></h3>
            <p className="mt-1.5 text-sm text-muted">{b.text}</p>
          </a>
        ))}
      </div>

      <section aria-labelledby="owasp-h">
        <div className="mb-3 flex flex-wrap items-baseline gap-x-3">
          <h2 id="owasp-h" className="text-lg font-semibold">OWASP API Security Top 10 <span className="gradient-text">2023</span></h2>
          <p className="text-sm text-muted">Test cases mapped to each category</p>
        </div>
        <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {OWASP_API.map((o, i) => {
            const n = counts.get(o.key) ?? 0;
            return (
              <li key={o.key}>
                <a href={owaspUrl(o.key)} target="_blank" rel="noopener noreferrer" className="card card-hover rise block h-full p-4" style={stagger(i)}>
                  <div className="flex items-start gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-[var(--border-a)] text-accent" style={{ background: "color-mix(in srgb, var(--g1) 10%, transparent)" }}>{ICONS[o.key]}</span>
                    <div className="min-w-0 flex-1">
                      <p className="mono text-[11px] text-faint">{o.key}:2023</p>
                      <h3 className="text-sm font-semibold leading-snug">{o.name}</h3>
                    </div>
                    <span className="tnum gradient-text text-2xl font-bold leading-none">{n}</span>
                  </div>
                  <p className="mt-2 text-xs text-muted">{o.desc}</p>
                  <div className="bar-track mt-3" role="progressbar" aria-valuenow={n} aria-valuemin={0} aria-valuemax={max} aria-label={`${n} test cases mapped to ${o.key}`}>
                    <div className="bar-fill" style={{ width: `${(n / max) * 100}%` }} />
                  </div>
                </a>
              </li>
            );
          })}
        </ul>
      </section>

      <div className="grid gap-4 md:grid-cols-3">
        <TopList title="Most-referenced CWE" rows={cwe} href={cweUrl} />
        <TopList title="Most-referenced ASVS 4.0" rows={asvs} href={() => ASVS_URL} />
        <TopList title="Most-referenced WSTG" rows={wstg} href={() => WSTG_URL} />
      </div>
    </div>
  );
}
