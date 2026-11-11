import { lazy, Suspense } from "react";
import Tabs from "../components/Tabs";
import { AlertIcon, Button, Skeleton } from "../components/ui";
import type { Analysis, Endpoint, Filters, Status, TestCase } from "../types";
import EndpointsTab from "./EndpointsTab";
import FindingsTab from "./FindingsTab";
import StandardsTab from "./StandardsTab";
import TestCasesTab from "./TestCasesTab";

const OverviewTab = lazy(() => import("./OverviewTab")); // pulls in recharts; loaded on demand

export const TABS = ["Overview", "Test Cases", "Endpoints", "Findings", "Standards"] as const;
export type Tab = (typeof TABS)[number];

interface Props {
  analysis: Analysis;
  cases: TestCase[];
  filtered: TestCase[];
  epMap: Map<string, Endpoint>;
  filters: Filters;
  setFilters: (f: Filters) => void;
  setStatus: (ids: string[], s: Status) => void;
  setNotes: (id: string, notes: string) => void;
  onNewUpload: () => void;
  tab: Tab;
  setTab: (t: Tab) => void;
  selEndpoint: string;
  setSelEndpoint: (id: string) => void;
}

function OverviewSkeleton() {
  return (
    <div className="space-y-4" role="status" aria-label="Loading charts">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-28" />)}</div>
      <div className="grid gap-4 lg:grid-cols-3"><Skeleton className="h-56" /><Skeleton className="h-56" /><Skeleton className="h-56" /></div>
      <Skeleton className="h-80" />
    </div>
  );
}

export default function ResultsPage({
  analysis, cases, filtered, epMap, filters, setFilters, setStatus, setNotes, onNewUpload, tab, setTab, selEndpoint, setSelEndpoint,
}: Props) {
  return (
    <>
      {/* Sticky tab bar, directly under the glass top bar */}
      <div className="topbar sticky top-14 z-20 !border-b-0">
        <div className="mx-auto flex w-full max-w-7xl items-center px-4 py-2">
          <Tabs tabs={TABS} value={tab} onChange={setTab} label="Results sections" counts={{ "Test Cases": cases.length, Findings: analysis.findings.length }} />
        </div>
      </div>

      <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-5" role="tabpanel" aria-label={tab}>
        {analysis.notice && (
          <div role="note" className="callout rise mb-4 flex flex-wrap items-start gap-3" style={{ "--c": "var(--sev-medium-dot)" } as React.CSSProperties}>
            <AlertIcon className="mt-0.5 h-5 w-5 shrink-0 text-[var(--sev-medium-dot)]" />
            <div className="min-w-0 flex-1">
              <p className="font-semibold">{analysis.notice.message}</p>
              {analysis.notice.hint && <p className="mt-0.5"><span className="font-medium">Hint:</span> {analysis.notice.hint}</p>}
              <p className="mt-0.5 text-xs text-muted">Showing the environment review below. Upload a collection (with this environment) to get test cases.</p>
            </div>
            <Button size="sm" onClick={onNewUpload}>Upload a collection</Button>
          </div>
        )}

        {/* key => fade + 8px rise on every tab change */}
        <div key={tab} className="rise">
          {tab === "Overview" && (
            <Suspense fallback={<OverviewSkeleton />}>
              <OverviewTab analysis={analysis} cases={cases} />
            </Suspense>
          )}
          {tab === "Test Cases" && (
            <TestCasesTab
              cases={cases} filtered={filtered} endpoints={analysis.endpoints} epMap={epMap}
              filters={filters} setFilters={setFilters} setStatus={setStatus} setNotes={setNotes} onNewUpload={onNewUpload}
            />
          )}
          {tab === "Endpoints" && (
            <EndpointsTab endpoints={analysis.endpoints} epMap={epMap} cases={cases} findings={analysis.findings}
              setStatus={setStatus} setNotes={setNotes} onNewUpload={onNewUpload} selId={selEndpoint} setSelId={setSelEndpoint} />
          )}
          {tab === "Findings" && <FindingsTab findings={analysis.findings} epMap={epMap} />}
          {tab === "Standards" && <StandardsTab cases={cases} />}
        </div>
      </main>
    </>
  );
}
