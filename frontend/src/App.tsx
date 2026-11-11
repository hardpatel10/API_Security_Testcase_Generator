import { useCallback, useEffect, useMemo, useState } from "react";
import { AboutModal, Atmosphere, Footer, Logo, LinkedInLink } from "./components/brand";
import CommandPalette from "./components/CommandPalette";
import ExportMenu from "./components/ExportMenu";
import { Button, CommandIcon, EmptyState, MoonIcon, ResetIcon, SunIcon, ToastProvider, UploadIcon, useToast } from "./components/ui";
import { applyFilters, filtersActive } from "./lib/filter";
import { load, save } from "./lib/storage";
import { useStore } from "./lib/store";
import ResultsPage, { TABS, type Tab } from "./pages/ResultsPage";
import UploadPage from "./pages/UploadPage";
import type { Endpoint } from "./types";

function isNotFoundPath(): boolean {
  const p = window.location.pathname;
  return p !== "/" && p !== "/index.html";
}

function Shell() {
  const toast = useToast();
  const onSaveError = useCallback(
    () => toast("Results are too large to save in this browser; progress will be lost on refresh.", "error"),
    [toast],
  );
  const store = useStore(onSaveError);
  const { analysis, merged } = store;
  const [dark, setDark] = useState(() => document.documentElement.classList.contains("dark"));
  const [tab, setTab] = useState<Tab>("Overview");
  const [selEndpoint, setSelEndpoint] = useState("");
  const [palette, setPalette] = useState(false);
  const [about, setAbout] = useState(false);
  const [notFound, setNotFound] = useState(isNotFoundPath);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    if (load<string>("apitp:theme") !== (dark ? "dark" : "light")) save("apitp:theme", dark ? "dark" : "light");
  }, [dark]);

  const epMap = useMemo(() => new Map<string, Endpoint>((analysis?.endpoints ?? []).map((e) => [e.id, e])), [analysis]);
  const filtered = useMemo(() => applyFilters(store.cases, epMap, store.filters), [store.cases, epMap, store.filters]);
  const filteredIds = useMemo(() => filtered.map((t) => t.id), [filtered]);

  // Ctrl/Cmd+K opens the quick-jump palette (only when there are results to jump around).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k" && analysis) {
        e.preventDefault();
        setPalette((p) => !p);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [analysis]);

  function reset() {
    if (window.confirm("Reset all statuses, notes and filters? The analysis stays loaded.")) {
      store.resetProgress();
      toast("Progress reset", "info");
    }
  }
  function newUpload() {
    const hasProgress = Object.values(store.progress).some((p) => p.status !== "Not Started" || p.notes);
    if (!hasProgress || window.confirm("Discard this analysis (including statuses and notes) and upload another file?")) {
      store.setAnalysis(null);
      setTab("Overview");
    }
  }
  function backToStart() {
    window.history.replaceState(null, "", "/");
    setNotFound(false);
  }

  const s = analysis?.summary;

  return (
    <div className="flex min-h-screen flex-col">
      <Atmosphere />
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-[90] focus:rounded-lg focus:bg-[var(--surface-solid)] focus:px-3 focus:py-2">Skip to content</a>

      {/* Sticky glass top bar */}
      <header className="topbar sticky top-0 z-30 h-14">
        <div className="mx-auto flex h-full w-full max-w-7xl items-center justify-between gap-2 px-4">
          <div className="flex min-w-0 items-center gap-2.5">
            <Logo className="h-8 w-8 shrink-0" />
            <span className="hidden truncate font-semibold tracking-tight sm:inline">API Security Test Planner</span>
            {analysis && !notFound && (
              <span className="mono hidden max-w-[16rem] truncate rounded-md border border-line bg-inset px-2 py-0.5 text-xs text-muted lg:inline" title={analysis.collection.name}>
                {analysis.collection.name}
              </span>
            )}
          </div>

          {analysis && s && !notFound && (
            <ul className="tnum hidden items-center gap-4 text-xs text-muted xl:flex" aria-label="Quick stats">
              <li><strong className="text-fg">{s.total_endpoints}</strong> endpoints</li>
              <li><strong className="text-fg">{store.cases.length}</strong> tests</li>
              <li><strong className="text-fg">{s.total_findings}</strong> findings</li>
            </ul>
          )}

          <div className="flex items-center gap-1.5 sm:gap-2">
            <span className="hidden lg:block"><LinkedInLink variant="button" /></span>
            {analysis && !notFound && (
              <>
                <Button size="sm" className="hidden sm:inline-flex" aria-label="Quick jump (Ctrl or Command + K)" aria-keyshortcuts="Control+K Meta+K" onClick={() => setPalette(true)}>
                  <CommandIcon className="h-3.5 w-3.5" /> <span className="tnum text-xs text-muted">Ctrl K</span>
                </Button>
                <Button size="sm" onClick={newUpload} title="Upload another file" aria-label="Upload another file"><UploadIcon /></Button>
                <Button size="sm" onClick={reset} title="Reset statuses, notes and filters" aria-label="Reset statuses, notes and filters"><ResetIcon /></Button>
              </>
            )}
            <Button size="sm" aria-label={dark ? "Switch to light theme" : "Switch to dark theme"} onClick={() => setDark((d) => !d)}>
              {dark ? <SunIcon /> : <MoonIcon />}
            </Button>
            {merged && !notFound && <ExportMenu analysis={merged} filteredIds={filteredIds} filtersOn={filtersActive(store.filters)} />}
          </div>
        </div>
      </header>

      <div id="main" className="flex flex-1 flex-col">
        {notFound ? (
          <main className="mx-auto flex w-full max-w-xl flex-1 items-center px-4 py-10">
            <div className="w-full">
              <EmptyState art="lost" title="404 — nothing here" hint={`There is no page at ${window.location.pathname}. The planner lives on the start page.`}
                action={<Button variant="primary" onClick={backToStart}>Back to the planner</Button>} />
            </div>
          </main>
        ) : analysis && merged ? (
          <ResultsPage
            analysis={analysis} cases={store.cases} filtered={filtered} epMap={epMap} filters={store.filters}
            setFilters={store.setFilters} setStatus={store.setStatus} setNotes={store.setNotes} onNewUpload={newUpload}
            tab={tab} setTab={setTab} selEndpoint={selEndpoint} setSelEndpoint={setSelEndpoint}
          />
        ) : (
          <UploadPage onAnalyzed={(a) => { store.setAnalysis(a); setTab("Overview"); setSelEndpoint(""); }} />
        )}
      </div>

      <Footer onAbout={() => setAbout(true)} />

      {palette && analysis && (
        <CommandPalette
          endpoints={analysis.endpoints}
          tabs={TABS}
          onClose={() => setPalette(false)}
          onTab={(t) => setTab(t as Tab)}
          onEndpoint={(id) => { setSelEndpoint(id); setTab("Endpoints"); }}
        />
      )}
      {about && <AboutModal onClose={() => setAbout(false)} />}
    </div>
  );
}

export default function App() {
  return (
    <ToastProvider>
      <Shell />
    </ToastProvider>
  );
}
