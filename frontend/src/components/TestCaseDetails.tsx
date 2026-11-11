import { useState } from "react";
import { stepsText } from "../lib/filter";
import { ASVS_URL, cweUrl, owaspUrl, WSTG_URL } from "../lib/standards";
import type { Endpoint, Status, TestCase } from "../types";
import { Collapse } from "./motion";
import { Button, Card, ChevronIcon, CopyIcon, ExternalIcon, MethodBadge, SeverityChip, StatusSelect, Tag, useToast } from "./ui";

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      return ok;
    } catch {
      return false;
    }
  }
}

export function CopyStepsButton({ tc }: { tc: TestCase }) {
  const toast = useToast();
  return (
    <Button
      size="sm"
      onClick={async (e) => {
        e.stopPropagation();
        toast((await copyText(stepsText(tc))) ? `Steps for ${tc.id} copied` : "Could not copy to the clipboard", "info");
      }}
    >
      <CopyIcon className="h-3.5 w-3.5" /> Copy steps
    </Button>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h4 className="eyebrow mb-1.5">{title}</h4>
      {children}
    </section>
  );
}

interface Props {
  tc: TestCase;
  endpoint?: Endpoint;
  onStatus: (ids: string[], s: Status) => void;
  onNotes: (id: string, notes: string) => void;
}

/** Expanded content of a test case: description, steps, data, expected result, standards, status and notes. */
export function TestCaseDetails({ tc, endpoint, onStatus, onNotes }: Props) {
  return (
    <div className="grid gap-5 p-4 text-sm sm:p-5 lg:grid-cols-3" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
      <div className="space-y-4 lg:col-span-2">
        <Section title="Description"><p className="text-muted">{tc.description}</p></Section>
        <Section title="How to test">
          <ol className="space-y-2">
            {tc.how_to_test.map((s, i) => (
              <li key={i} className="flex gap-2.5"><span className="step-n tnum mt-0.5">{i + 1}</span><span>{s}</span></li>
            ))}
          </ol>
        </Section>
        <Section title="Sample test data (authorized testing only)">
          <pre className="codeblock">{tc.test_data}</pre>
        </Section>
        <Section title="Expected secure result"><p className="callout callout-pass">{tc.expected_result}</p></Section>
      </div>
      <div className="space-y-4">
        <Section title="Status">
          <div className="flex flex-wrap items-center gap-2">
            <StatusSelect label={`Status for ${tc.id}`} value={tc.status} onChange={(s) => onStatus([tc.id], s)} />
            <CopyStepsButton tc={tc} />
          </div>
        </Section>
        <Section title="Notes">
          <textarea
            aria-label={`Notes for ${tc.id}`}
            className="input min-h-[5.5rem] w-full"
            placeholder="Add evidence, request IDs, observations…"
            value={tc.notes}
            onChange={(e) => onNotes(tc.id, e.target.value)}
          />
        </Section>
        <Section title="Standard references">
          <ul className="space-y-2">
            <li className="flex flex-wrap items-center gap-1.5">
              <span className="w-16 text-xs text-faint">OWASP API</span>
              <a className="inline-flex items-center gap-1 text-accent hover:underline" href={owaspUrl(tc.owasp_api)} target="_blank" rel="noopener noreferrer">
                {tc.owasp_api} <ExternalIcon />
              </a>
            </li>
            <li className="flex flex-wrap items-center gap-1.5">
              <span className="w-16 text-xs text-faint">CWE</span>
              {tc.cwe.map((c) => <Tag key={c} href={cweUrl(c)} title="Open on cwe.mitre.org">{c}</Tag>)}
            </li>
            <li className="flex flex-wrap items-center gap-1.5">
              <span className="w-16 text-xs text-faint">ASVS 4.0</span>
              {tc.asvs.map((c) => <Tag key={c} href={ASVS_URL} title="OWASP ASVS 4.0">{c}</Tag>)}
            </li>
            <li className="flex flex-wrap items-center gap-1.5">
              <span className="w-16 text-xs text-faint">WSTG</span>
              {tc.wstg.map((c) => <Tag key={c} href={WSTG_URL} title="OWASP WSTG">{c}</Tag>)}
            </li>
          </ul>
        </Section>
        {endpoint && (
          <Section title="Endpoint">
            <div className="flex items-start gap-2"><MethodBadge method={endpoint.method} /><span className="mono break-all text-xs">{endpoint.url}</span></div>
          </Section>
        )}
      </div>
    </div>
  );
}

/** Self-contained collapsible card (used on the Endpoints tab). */
export function TestCaseCard({ tc, endpoint, onStatus, onNotes }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <Card className="overflow-hidden">
      <div className="flex items-center gap-3 px-4 py-2.5">
        <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} className="flex min-w-0 flex-1 items-center gap-3 rounded-md py-1 text-left">
          <ChevronIcon open={open} className="h-4 w-4 text-faint" />
          <span className="mono text-xs text-faint">{tc.id}</span>
          <span className="min-w-0 flex-1 truncate text-sm font-medium">{tc.title}</span>
        </button>
        <span className="hidden sm:inline"><Tag>{tc.owasp_api.split(":")[0]}</Tag></span>
        <SeverityChip severity={tc.severity} />
        <StatusSelect label={`Status for ${tc.id}`} value={tc.status} onChange={(s) => onStatus([tc.id], s)} />
      </div>
      <Collapse open={open}>
        <div className="border-t border-line">
          <TestCaseDetails tc={tc} endpoint={endpoint} onStatus={onStatus} onNotes={onNotes} />
        </div>
      </Collapse>
    </Card>
  );
}
