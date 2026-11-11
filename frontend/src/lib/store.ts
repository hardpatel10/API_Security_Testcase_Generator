import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { DEFAULT_FILTERS, type Analysis, type Filters, type Progress, type Status, type TestCase } from "../types";
import { load, remove, save } from "./storage";

const KEY_ANALYSIS = "apitp:analysis:v1";
const KEY_PROGRESS = "apitp:progress:v1";
const KEY_FILTERS = "apitp:filters:v1";

function validAnalysis(a: Analysis | null): a is Analysis {
  return !!a && Array.isArray(a.test_cases) && Array.isArray(a.endpoints) && Array.isArray(a.findings) && !!a.summary;
}

/** App state (analysis + user progress + filters), persisted to localStorage. */
export function useStore(onSaveError: () => void) {
  const [analysis, setAnalysisState] = useState<Analysis | null>(() => {
    const a = load<Analysis>(KEY_ANALYSIS);
    return validAnalysis(a) ? a : null;
  });
  const [progress, setProgress] = useState<Progress>(() => load<Progress>(KEY_PROGRESS) ?? {});
  const [filters, setFilters] = useState<Filters>(() => ({ ...DEFAULT_FILTERS, ...(load<Filters>(KEY_FILTERS) ?? {}) }));
  const warned = useRef(false);

  useEffect(() => {
    if (analysis) {
      if (!save(KEY_ANALYSIS, analysis) && !warned.current) {
        warned.current = true;
        onSaveError();
      }
    } else remove(KEY_ANALYSIS);
  }, [analysis, onSaveError]);
  useEffect(() => void save(KEY_PROGRESS, progress), [progress]);
  useEffect(() => void save(KEY_FILTERS, filters), [filters]);

  /** Test cases merged with the user's status/notes. */
  const cases: TestCase[] = useMemo(
    () =>
      (analysis?.test_cases ?? []).map((t) => {
        const p = progress[t.id];
        return p ? { ...t, status: p.status, notes: p.notes } : t;
      }),
    [analysis, progress],
  );

  const setAnalysis = useCallback((a: Analysis | null) => {
    setAnalysisState(a);
    setProgress({});
    setFilters(DEFAULT_FILTERS);
    warned.current = false;
  }, []);

  const setStatus = useCallback((ids: string[], status: Status) => {
    setProgress((p) => {
      const next = { ...p };
      for (const id of ids) next[id] = { status, notes: next[id]?.notes ?? "" };
      return next;
    });
  }, []);

  const setNotes = useCallback((id: string, notes: string) => {
    setProgress((p) => ({ ...p, [id]: { status: p[id]?.status ?? "Not Started", notes } }));
  }, []);

  const resetProgress = useCallback(() => {
    setProgress({});
    setFilters(DEFAULT_FILTERS);
  }, []);

  /** The analysis with the user's current status/notes merged in (what gets exported). */
  const merged: Analysis | null = useMemo(() => (analysis ? { ...analysis, test_cases: cases } : null), [analysis, cases]);

  return { analysis, merged, cases, progress, filters, setFilters, setAnalysis, setStatus, setNotes, resetProgress };
}
