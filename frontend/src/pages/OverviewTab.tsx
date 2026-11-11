import { useEffect, useMemo, useState, type CSSProperties, type ReactNode } from "react";
import { Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { useCountUp } from "../components/motion";
import { Card } from "../components/ui";
import { OWASP_API } from "../lib/standards";
import { SEVERITIES, STATUSES, type Analysis, type TestCase } from "../types";

const SEV_COLOR: Record<string, string> = {
  High: "var(--sev-high-dot)", Medium: "var(--sev-medium-dot)", Low: "var(--sev-low-dot)", Info: "var(--sev-info-dot)",
};
const STATUS_COLOR: Record<string, string> = {
  "Not Started": "var(--st-notstarted)", Pass: "var(--st-pass)", Fail: "var(--st-fail)", "N/A": "var(--st-na)",
};
const TOOLTIP_STYLE: CSSProperties = {
  background: "var(--overlay)", border: "1px solid var(--border-strong)", borderRadius: 12, color: "var(--text)",
  boxShadow: "var(--shadow)", fontSize: 12.5, padding: "6px 10px",
};

const stagger = (i: number): CSSProperties => ({ animationDelay: `${i * 70}ms` });

/** Risk score 0-100 from finding severities (higher = riskier). Saturating, so a few Highs matter most. */
export function riskScore(f: Record<string, number>): number {
  const points = (f.High ?? 0) * 10 + (f.Medium ?? 0) * 4 + (f.Low ?? 0);
  return Math.round(100 * (1 - Math.exp(-points / 40)));
}
const band = (s: number) => (s >= 75 ? "Critical" : s >= 50 ? "Elevated" : s >= 25 ? "Moderate" : "Low");

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) return null;
  const max = Math.max(...values, 1);
  const w = 84, h = 32;
  const pts = values.map((v, i) => [(i / (values.length - 1)) * w, h - 3 - (v / max) * (h - 8)] as const);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-8 w-[84px]" aria-hidden>
      <defs>
        <linearGradient id="spark-g" x1="0" x2="1"><stop offset="0" style={{ stopColor: "var(--g1)" }} /><stop offset="1" style={{ stopColor: "var(--g3)" }} /></linearGradient>
        <linearGradient id="spark-a" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style={{ stopColor: "var(--g2)", stopOpacity: 0.3 }} /><stop offset="1" style={{ stopColor: "var(--g2)", stopOpacity: 0 }} /></linearGradient>
      </defs>
      <path d={`${line} L${w} ${h} L0 ${h} Z`} fill="url(#spark-a)" />
      <path d={line} fill="none" stroke="url(#spark-g)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function MiniRing({ pct }: { pct: number }) {
  const C = 2 * Math.PI * 13;
  return (
    <svg viewBox="0 0 32 32" className="h-9 w-9 -rotate-90" aria-hidden>
      <defs><linearGradient id="mini-g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" style={{ stopColor: "var(--g1)" }} /><stop offset="1" style={{ stopColor: "var(--g3)" }} /></linearGradient></defs>
      <circle cx="16" cy="16" r="13" fill="none" stroke="var(--border)" strokeWidth="4" />
      <circle cx="16" cy="16" r="13" fill="none" stroke="url(#mini-g)" strokeWidth="4" strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C * (1 - pct / 100)} style={{ transition: "stroke-dashoffset .6s ease" }} />
    </svg>
  );
}

function StatCard({ label, value, hint, viz, tone, index }: { label: string; value: number; hint?: string; viz?: ReactNode; tone?: "danger"; index: number }) {
  const n = useCountUp(value);
  return (
    <Card className="card-hover rise p-4" style={stagger(index)}>
      <div className="flex min-h-9 items-start justify-between gap-2">
        <p className="eyebrow">{label}</p>
        {viz}
      </div>
      <p className={`tnum mt-1 text-4xl font-bold leading-none tracking-tight ${tone === "danger" ? "" : "gradient-text"}`}
        style={tone === "danger" ? { color: "var(--sev-high-fg)" } : undefined}>{n}</p>
      {hint && <p className="mt-2 truncate text-xs text-muted" title={hint}>{hint}</p>}
    </Card>
  );
}

function Panel({ title, subtitle, children, className = "", index = 0 }: { title: string; subtitle?: string; children: ReactNode; className?: string; index?: number }) {
  return (
    <Card className={`rise p-4 sm:p-5 ${className}`} style={stagger(index)}>
      <h3 className="text-sm font-semibold">{title}</h3>
      {subtitle ? <p className="mb-3 text-xs text-muted">{subtitle}</p> : <div className="mb-3" />}
      {children}
    </Card>
  );
}

function Legend({ items }: { items: { name: string; value: number; color: string }[] }) {
  return (
    <ul className="space-y-1.5 text-sm">
      {items.map((i) => (
        <li key={i.name} className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: i.color, boxShadow: `0 0 8px ${i.color}` }} />
          <span className="flex-1 text-muted">{i.name}</span>
          <span className="tnum font-semibold">{i.value}</span>
        </li>
      ))}
    </ul>
  );
}

function Donut({ data, center }: { data: { name: string; value: number; color: string }[]; center: string }) {
  const total = data.reduce((s, d) => s + d.value, 0);
  const shown = total ? data.filter((d) => d.value > 0) : [{ name: "none", value: 1, color: "var(--border)" }];
  const n = useCountUp(total);
  return (
    <div className="flex flex-wrap items-center gap-5">
      <div className="relative h-40 w-40 shrink-0" role="img" aria-label={`${center}: ${data.map((d) => `${d.name} ${d.value}`).join(", ")}`}>
        <ResponsiveContainer>
          <PieChart>
            <Pie data={shown} dataKey="value" innerRadius={52} outerRadius={74} paddingAngle={total ? 4 : 0} cornerRadius={total ? 6 : 0} stroke="none" isAnimationActive={false}>
              {shown.map((d) => <Cell key={d.name} fill={d.color} />)}
            </Pie>
            {total > 0 && <Tooltip contentStyle={TOOLTIP_STYLE} itemStyle={{ color: "var(--text)" }} />}
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="tnum gradient-text text-2xl font-bold">{n}</span>
          <span className="text-[11px] text-muted">{center}</span>
        </div>
      </div>
      <div className="min-w-[8rem] flex-1"><Legend items={data} /></div>
    </div>
  );
}

function RiskGauge({ score }: { score: number }) {
  const n = useCountUp(score);
  const R = 52, C = 2 * Math.PI * R, arc = 0.75; // 270° gauge
  return (
    <div className="flex items-center gap-5">
      <div className="relative h-40 w-40 shrink-0" role="img" aria-label={`Risk score ${score} out of 100, ${band(score)}`}>
        <svg viewBox="0 0 140 140" className="h-full w-full rotate-[135deg]" aria-hidden>
          <defs><linearGradient id="risk-g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" style={{ stopColor: "var(--g3)" }} /><stop offset=".5" style={{ stopColor: "var(--g2)" }} /><stop offset="1" style={{ stopColor: "var(--sev-high-dot)" }} /></linearGradient></defs>
          <circle cx="70" cy="70" r={R} fill="none" stroke="var(--border)" strokeWidth="10" strokeLinecap="round" strokeDasharray={`${C * arc} ${C}`} />
          <circle cx="70" cy="70" r={R} fill="none" stroke="url(#risk-g)" strokeWidth="10" strokeLinecap="round"
            strokeDasharray={`${C * arc * (score / 100)} ${C}`} style={{ transition: "stroke-dasharray .9s cubic-bezier(.2,.8,.2,1)", filter: "drop-shadow(0 0 6px var(--glow))" }} />
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="tnum gradient-text text-4xl font-bold leading-none">{n}</span>
          <span className="mt-1 text-[11px] text-muted">of 100</span>
        </div>
      </div>
      <div className="min-w-[7rem] flex-1">
        <p className="eyebrow">Risk level</p>
        <p className="text-xl font-semibold">{band(score)}</p>
        <p className="mt-1 text-xs text-muted">Weighted from static findings: High ×10, Medium ×4, Low ×1.</p>
      </div>
    </div>
  );
}

function useNarrow(): boolean {
  const q = "(max-width: 639px)";
  const [narrow, setNarrow] = useState(() => window.matchMedia(q).matches);
  useEffect(() => {
    const m = window.matchMedia(q);
    const on = () => setNarrow(m.matches);
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return narrow;
}

export default function OverviewTab({ analysis, cases }: { analysis: Analysis; cases: TestCase[] }) {
  const s = analysis.summary;
  const narrow = useNarrow();
  const high = s.findings_by_severity.High ?? 0;
  const sevData = SEVERITIES.map((k) => ({ name: k, value: s.findings_by_severity[k] ?? 0, color: SEV_COLOR[k] }));
  const score = riskScore(s.findings_by_severity);

  const owaspData = useMemo(() => {
    const counts = new Map<string, number>();
    for (const c of cases) counts.set(c.owasp_api.split(":")[0], (counts.get(c.owasp_api.split(":")[0]) ?? 0) + 1);
    return OWASP_API.map((o) => ({ key: o.key, name: `${o.key} ${o.name}`, count: counts.get(o.key) ?? 0 }));
  }, [cases]);

  const statusData = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const c of cases) counts[c.status] = (counts[c.status] ?? 0) + 1;
    return STATUSES.map((k) => ({ name: k, value: counts[k] ?? 0, color: STATUS_COLOR[k] }));
  }, [cases]);
  const done = statusData.filter((d) => d.name !== "Not Started").reduce((n, d) => n + d.value, 0);
  const pct = cases.length ? Math.round((done / cases.length) * 100) : 0;

  const perEndpoint = useMemo(() => {
    const m = new Map<string, number>();
    for (const c of cases) m.set(c.endpoint_id, (m.get(c.endpoint_id) ?? 0) + 1);
    return analysis.endpoints.map((e) => m.get(e.id) ?? 0);
  }, [cases, analysis.endpoints]);

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard index={0} label="Endpoints" value={s.total_endpoints} hint={analysis.collection.name} viz={<Sparkline values={perEndpoint} />} />
        <StatCard index={1} label="Test cases" value={cases.length} hint={`${pct}% reviewed`} viz={<MiniRing pct={pct} />} />
        <StatCard index={2} label="Findings" value={s.total_findings}
          hint={s.environment_findings ? `${s.environment_findings} in the environment file` : "static misconfigurations"} />
        <StatCard index={3} label="High severity" value={high} tone="danger" hint="high-severity findings"
          viz={high > 0 ? <span className="chip sev-high"><span className="dot" />Act first</span> : undefined} />
      </div>

      {analysis.collection.warnings.length > 0 && (
        <div role="note" className="callout rise" style={{ "--c": "var(--sev-medium-dot)" } as CSSProperties}>
          {analysis.collection.warnings.map((w, i) => <p key={i}>{w}</p>)}
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel index={4} title="Risk score" subtitle="Overall exposure from static findings"><RiskGauge score={score} /></Panel>
        <Panel index={5} title="Findings by severity" subtitle="Static misconfigurations"><Donut data={sevData} center="findings" /></Panel>
        <Panel index={6} title="Test progress" subtitle={`${pct}% of test cases reviewed`}>
          <Donut data={statusData} center="test cases" />
        </Panel>
      </div>

      <Panel index={7} title="Test cases by OWASP API Security category (2023)" subtitle="Where the generated tests concentrate">
        <div className="h-[22rem] text-muted" role="img" aria-label={`Test cases per OWASP category: ${owaspData.map((d) => `${d.key} ${d.count}`).join(", ")}`}>
          <ResponsiveContainer>
            <BarChart data={owaspData} layout="vertical" margin={{ left: 4, right: 24 }} barCategoryGap={8}>
              <defs>
                <linearGradient id="bar-g" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" style={{ stopColor: "var(--g1)" }} /><stop offset="60%" style={{ stopColor: "var(--g2)" }} /><stop offset="100%" style={{ stopColor: "var(--g3)" }} />
                </linearGradient>
              </defs>
              <XAxis type="number" allowDecimals={false} tick={{ fill: "var(--muted)", fontSize: 12 }} stroke="var(--border)" />
              <YAxis type="category" dataKey={narrow ? "key" : "name"} width={narrow ? 56 : 310} interval={0} tick={{ fill: "var(--muted)", fontSize: 12 }} stroke="var(--border)"
                tickFormatter={(v: string) => (v.length > 60 ? v.slice(0, 59) + "…" : v)} />
              <Tooltip cursor={{ fill: "var(--row-hover)" }} contentStyle={TOOLTIP_STYLE} itemStyle={{ color: "var(--text)" }} labelStyle={{ color: "var(--muted)" }} />
              <Bar dataKey="count" name="Test cases" fill="url(#bar-g)" radius={[0, 8, 8, 0]} isAnimationActive={false} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Panel>
    </div>
  );
}
