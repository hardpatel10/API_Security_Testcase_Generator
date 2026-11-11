import { useEffect, useRef, useState } from "react";
import { downloadBlob, exportReport } from "../api";
import type { Analysis } from "../types";
import { Button, ChevronIcon, DownloadIcon, SpinnerIcon, useToast } from "./ui";

interface Props {
  analysis: Analysis; // already merged with the user's current status/notes
  filteredIds: string[];
  filtersOn: boolean;
}

export default function ExportMenu({ analysis, filteredIds, filtersOn }: Props) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("mousedown", onDoc); document.removeEventListener("keydown", onKey); };
  }, [open]);

  async function run(ids?: string[]) {
    setOpen(false);
    setBusy(true);
    try {
      const { blob, filename } = await exportReport(analysis, ids);
      downloadBlob(blob, filename);
      toast(`Report downloaded: ${filename}`, "success");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Export failed.", "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative" ref={ref}>
      <Button variant="primary" aria-haspopup="menu" aria-expanded={open} loading={busy} onClick={() => setOpen((o) => !o)}>
        {busy ? <SpinnerIcon /> : <DownloadIcon />}
        <span className="hidden sm:inline">Download Excel</span>
        <span className="sm:hidden">Excel</span>
        <ChevronIcon open={open} className="h-3.5 w-3.5 -rotate-90" />
      </Button>
      {open && (
        <div role="menu" className="overlay pop-in absolute right-0 z-50 mt-2 w-72 overflow-hidden">
          <button role="menuitem" type="button" className="block w-full px-4 py-3 text-left text-sm transition-colors hover:bg-[var(--row-hover)]" onClick={() => run()}>
            <span className="font-semibold">Export all</span>
            <span className="block text-xs text-muted">All {analysis.test_cases.length} test cases, findings and standards</span>
          </button>
          <button
            role="menuitem"
            type="button"
            disabled={filteredIds.length === 0}
            className="block w-full border-t border-line px-4 py-3 text-left text-sm transition-colors hover:bg-[var(--row-hover)] disabled:opacity-50"
            onClick={() => run(filteredIds)}
          >
            <span className="font-semibold">Export filtered</span>
            <span className="block text-xs text-muted">
              {filteredIds.length} of {analysis.test_cases.length} test cases{filtersOn ? " (current filters)" : " (no filters active)"}
            </span>
          </button>
        </div>
      )}
    </div>
  );
}
