import { Fragment, useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { DataTable } from "../components/DataTable";
import { Collapse } from "../components/motion";
import { TestCaseDetails } from "../components/TestCaseDetails";
import {
  Button, Card, ChevronIcon, CloseIcon, EmptyState, FilterIcon, MethodBadge, SearchIcon, SeverityChip, StatusSelect, Tag,
} from "../components/ui";
import { filtersActive } from "../lib/filter";
import { cweUrl, owaspKey, owaspUrl } from "../lib/standards";
import { DEFAULT_FILTERS, SEVERITIES, STATUSES, type Endpoint, type Filters, type SortKey, type Status, type TestCase } from "../types";

const PAGE_SIZE = 25;

interface Props {
  cases: TestCase[];
  filtered: TestCase[];
  endpoints: Endpoint[];
  epMap: Map<string, Endpoint>;
  filters: Filters;
  setFilters: (f: Filters) => void;
  setStatus: (ids: string[], s: Status) => void;
  setNotes: (id: string, notes: string) => void;
  onNewUpload: () => void;
}

function FilterSelect({ label, value, onChange, full, children }: { label: string; value: string; onChange: (v: string) => void; full?: boolean; children: React.ReactNode }) {
  return (
    <select aria-label={label} className={`input ${full ? "w-full" : "max-w-[10.5rem]"}`} value={value} onChange={(e) => onChange(e.target.value)}>
      <option value="">{label}: all</option>
      {children}
    </select>
  );
}

interface ControlProps {
  filters: Filters;
  set: <K extends keyof Filters>(k: K, v: Filters[K]) => void;
  owaspOptions: string[];
  methods: string[];
  endpoints: Endpoint[];
  full?: boolean;
}

/** The non-search filter controls; rendered inline on wide screens and inside the drawer on small ones. */
function FilterControls({ filters, set, owaspOptions, methods, endpoints, full }: ControlProps) {
  return (
    <>
      <FilterSelect full={full} label="Severity" value={filters.severity} onChange={(v) => set("severity", v)}>
        {SEVERITIES.map((s) => <option key={s}>{s}</option>)}
      </FilterSelect>
      <FilterSelect full={full} label="OWASP" value={filters.owasp} onChange={(v) => set("owasp", v)}>
        {owaspOptions.map((o) => <option key={o} value={o}>{o.length > 40 ? o.slice(0, 39) + "…" : o}</option>)}
      </FilterSelect>
      <FilterSelect full={full} label="Method" value={filters.method} onChange={(v) => set("method", v)}>
        {methods.map((m) => <option key={m}>{m}</option>)}
      </FilterSelect>
      <FilterSelect full={full} label="Status" value={filters.status} onChange={(v) => set("status", v)}>
        {STATUSES.map((s) => <option key={s}>{s}</option>)}
      </FilterSelect>
      <FilterSelect full={full} label="Endpoint" value={filters.endpoint} onChange={(v) => set("endpoint", v)}>
        {endpoints.map((e) => <option key={e.id} value={e.id}>{`${e.id} ${e.method} ${e.url.replace(/^https?:\/\/[^/]+/, "").slice(0, 30)}`}</option>)}
      </FilterSelect>
      <select aria-label="Sort by" className={`input ${full ? "w-full" : ""}`} value={filters.sort} onChange={(e) => set("sort", e.target.value as SortKey)}>
        <option value="id">Sort: ID</option>
        <option value="severity">Sort: Severity</option>
        <option value="endpoint">Sort: Endpoint</option>
      </select>
      <label className="flex cursor-pointer items-center gap-2 text-sm">
        <input type="checkbox" className="h-4 w-4 accent-[var(--g2)]" checked={filters.group} onChange={(e) => set("group", e.target.checked)} />
        Group by endpoint
      </label>
    </>
  );
}

function FilterDrawer({ onClose, onClear, count, children }: { onClose: () => void; onClear: () => void; count: number; children: React.ReactNode }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: globalThis.KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-[75] md:hidden" role="dialog" aria-modal="true" aria-label="Filters">
      <button type="button" aria-label="Close filters" tabIndex={-1} className="fade-in absolute inset-0 bg-black/55 backdrop-blur-sm" onClick={onClose} />
      <div className="overlay absolute inset-y-0 right-0 flex w-[min(22rem,92vw)] flex-col gap-3 overflow-y-auto !rounded-r-none p-4" style={{ animation: "toast-in 0.26s cubic-bezier(0.2,0.8,0.2,1) both" }}>
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Filters{count ? ` (${count})` : ""}</h2>
          <button ref={closeRef} type="button" onClick={onClose} aria-label="Close filters" className="rounded-lg p-1.5 text-muted hover:bg-inset hover:text-fg"><CloseIcon /></button>
        </div>
        {children}
        <div className="mt-auto flex gap-2">
          <Button className="flex-1" onClick={onClear}>Clear</Button>
          <Button variant="primary" className="flex-1" onClick={onClose}>Show results</Button>
        </div>
      </div>
    </div>
  );
}

export default function TestCasesTab({ cases, filtered, endpoints, epMap, filters, setFilters, setStatus, setNotes, onNewUpload }: Props) {
  const [page, setPage] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [drawer, setDrawer] = useState(false);
  const tbodyRef = useRef<HTMLTableSectionElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const set = <K extends keyof Filters>(k: K, v: Filters[K]) => setFilters({ ...filters, [k]: v });

  // "/" focuses the search box (unless the user is already typing somewhere).
  useEffect(() => {
    const onKey = (e: globalThis.KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (e.key !== "/" || e.ctrlKey || e.metaKey || e.altKey) return;
      if (el.closest("input, textarea, select, [contenteditable]")) return;
      e.preventDefault();
      searchRef.current?.focus();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  // Back to page 1 when the filters change.
  const filterKey = JSON.stringify(filters);
  useEffect(() => setPage(0), [filterKey]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const cur = Math.min(page, pageCount - 1);
  const rows = filtered.slice(cur * PAGE_SIZE, (cur + 1) * PAGE_SIZE);

  const owaspOptions = useMemo(() => [...new Set(cases.map((c) => c.owasp_api))].sort((a, b) => parseInt(a.slice(3)) - parseInt(b.slice(3))), [cases]);
  const methods = useMemo(() => [...new Set(endpoints.map((e) => e.method))].sort(), [endpoints]);

  const pageIds = rows.map((r) => r.id);
  const allPageSelected = pageIds.length > 0 && pageIds.every((id) => selected.has(id));
  const active = filtersActive(filters);
  const activeCount = [filters.severity, filters.owasp, filters.method, filters.status, filters.endpoint].filter(Boolean).length;
  const clearFilters = () => setFilters({ ...DEFAULT_FILTERS, sort: filters.sort, group: filters.group });

  function toggleSelect(id: string) {
    setSelected((s) => {
      const n = new Set(s);
      if (n.has(id)) n.delete(id); else n.add(id);
      return n;
    });
  }
  function togglePage() {
    setSelected((s) => {
      const n = new Set(s);
      if (allPageSelected) pageIds.forEach((id) => n.delete(id)); else pageIds.forEach((id) => n.add(id));
      return n;
    });
  }

  function onKeyDown(e: KeyboardEvent<HTMLTableSectionElement>) {
    const row = (e.target as HTMLElement).closest<HTMLElement>("tr[data-row]");
    if (!row || e.target !== row) return;
    const all = Array.from(tbodyRef.current?.querySelectorAll<HTMLElement>("tr[data-row]") ?? []);
    const i = all.indexOf(row);
    const focus = (n: number) => { e.preventDefault(); all[Math.max(0, Math.min(all.length - 1, n))]?.focus(); };
    if (e.key === "ArrowDown") focus(i + 1);
    else if (e.key === "ArrowUp") focus(i - 1);
    else if (e.key === "Home") focus(0);
    else if (e.key === "End") focus(all.length - 1);
    else if (e.key === "Enter") { e.preventDefault(); setOpenId((o) => (o === row.dataset.row ? null : row.dataset.row ?? null)); }
    else if (e.key === " ") { e.preventDefault(); toggleSelect(row.dataset.row ?? ""); }
  }

  const selectedCount = selected.size;

  if (cases.length === 0) {
    return (
      <EmptyState
        art="upload"
        title="No test cases yet"
        hint="Test cases are generated from the requests in an API collection. Upload a collection to get them."
        action={<Button variant="primary" onClick={onNewUpload}>Upload a collection</Button>}
      />
    );
  }

  const controlProps = { filters, set, owaspOptions, methods, endpoints };

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <Card className="flex flex-wrap items-center gap-2 p-3">
        <div className="relative min-w-[10rem] flex-1">
          <SearchIcon className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-faint" />
          <input
            ref={searchRef}
            type="search"
            aria-label="Search test cases (press / to focus)"
            aria-keyshortcuts="/"
            className="input w-full !pl-8 !pr-8"
            placeholder="Search by ID, title, URL, CWE, notes…"
            value={filters.search}
            onChange={(e) => set("search", e.target.value)}
          />
          <kbd className="tag pointer-events-none absolute right-2 top-1.5 hidden sm:block" aria-hidden>/</kbd>
        </div>
        <Button className="md:hidden" onClick={() => setDrawer(true)} aria-haspopup="dialog">
          <FilterIcon /> Filters{activeCount ? ` (${activeCount})` : ""}
        </Button>
        <div className="hidden flex-wrap items-center gap-2 md:flex"><FilterControls {...controlProps} /></div>
        {active && <Button size="sm" className="hidden md:inline-flex" onClick={clearFilters}>Clear filters</Button>}
      </Card>
      {drawer && (
        <FilterDrawer onClose={() => setDrawer(false)} onClear={clearFilters} count={activeCount}>
          <FilterControls {...controlProps} full />
        </FilterDrawer>
      )}

      <p className="text-sm text-muted" aria-live="polite">
        Showing <strong className="tnum text-fg">{filtered.length}</strong> of <strong className="tnum text-fg">{cases.length}</strong> test cases
      </p>

      {filtered.length === 0 ? (
        <EmptyState
          art="search"
          title="No test cases match your filters"
          hint="Try a different search term or clear the filters."
          action={<Button onClick={() => setFilters({ ...DEFAULT_FILTERS })}>Clear filters</Button>}
        />
      ) : (
        <>
          {/* ≥ md: table */}
          <DataTable caption="Test cases. Use arrow keys to move between rows, Enter to expand, Space to select.">
            <thead>
              <tr>
                <th className="w-8"><input type="checkbox" aria-label="Select all rows on this page" className="h-4 w-4 accent-[var(--g2)]" checked={allPageSelected} onChange={togglePage} /></th>
                <th className="w-24">TC ID</th>
                <th>Endpoint</th>
                <th>Test to perform</th>
                <th>Category</th>
                <th>OWASP API / CWE / ASVS</th>
                <th>Severity</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody ref={tbodyRef} onKeyDown={onKeyDown}>
              {rows.map((t, idx) => {
                const ep = epMap.get(t.endpoint_id);
                const open = openId === t.id;
                const newGroup = filters.group && (idx === 0 || rows[idx - 1].endpoint_id !== t.endpoint_id);
                return (
                  <Fragment key={t.id}>
                    {newGroup && ep && (
                      <tr>
                        <td colSpan={8} className="border-b border-line bg-inset px-3 py-2 text-sm font-semibold">
                          <span className="mono mr-2 text-xs text-faint">{ep.id}</span>
                          <MethodBadge method={ep.method} /> <span className="mono ml-2 break-all text-xs">{ep.url}</span>
                          <span className="ml-2 font-normal text-muted">— {ep.name}</span>
                        </td>
                      </tr>
                    )}
                    <tr
                      data-row={t.id}
                      tabIndex={0}
                      aria-expanded={open}
                      onClick={() => setOpenId(open ? null : t.id)}
                      className={`row cursor-pointer ${idx % 2 ? "alt" : ""}`}
                    >
                      <td className="td" onClick={(e) => e.stopPropagation()}>
                        <input type="checkbox" className="h-4 w-4 accent-[var(--g2)]" aria-label={`Select ${t.id}`} checked={selected.has(t.id)} onChange={() => toggleSelect(t.id)} />
                      </td>
                      <td className="td mono whitespace-nowrap text-xs text-muted"><ChevronIcon open={open} className="mr-1 inline h-3 w-3 text-faint" />{t.id}</td>
                      <td className="td">
                        {ep && (
                          <div className="flex items-start gap-2">
                            <MethodBadge method={ep.method} />
                            <div className="min-w-0">
                              <div className="mono break-all text-xs">{ep.url}</div>
                              <div className="text-xs text-faint">{ep.name}</div>
                            </div>
                          </div>
                        )}
                      </td>
                      <td className="td font-medium">{t.title}</td>
                      <td className="td text-muted">{t.category}</td>
                      <td className="td">
                        <div className="flex flex-wrap gap-1">
                          <Tag href={owaspUrl(t.owasp_api)} title={t.owasp_api}>{owaspKey(t.owasp_api)}</Tag>
                          {t.cwe.slice(0, 2).map((c) => <Tag key={c} href={cweUrl(c)} title="CWE">{c}</Tag>)}
                          {t.asvs[0] && <Tag title="OWASP ASVS 4.0">ASVS {t.asvs[0]}</Tag>}
                        </div>
                      </td>
                      <td className="td"><SeverityChip severity={t.severity} /></td>
                      <td className="td" onClick={(e) => e.stopPropagation()}>
                        <StatusSelect label={`Status for ${t.id}`} value={t.status} onChange={(s) => setStatus([t.id], s)} />
                      </td>
                    </tr>
                    <tr>
                      <td colSpan={8} className="p-0">
                        <Collapse open={open}>
                          <div className="border-b border-line bg-[var(--inset)]">
                            <TestCaseDetails tc={t} endpoint={ep} onStatus={setStatus} onNotes={setNotes} />
                          </div>
                        </Collapse>
                      </td>
                    </tr>
                  </Fragment>
                );
              })}
            </tbody>
          </DataTable>

          {/* < md: cards */}
          <ul className="space-y-2.5 md:hidden" aria-label="Test cases">
            {rows.map((t, idx) => {
              const ep = epMap.get(t.endpoint_id);
              const open = openId === t.id;
              const newGroup = filters.group && (idx === 0 || rows[idx - 1].endpoint_id !== t.endpoint_id);
              return (
                <Fragment key={t.id}>
                  {newGroup && ep && (
                    <li className="rounded-lg bg-inset px-3 py-2 text-xs font-semibold">
                      {ep.id} · {ep.method} <span className="mono break-all font-normal">{ep.url}</span>
                    </li>
                  )}
                  <li>
                    <Card className="overflow-hidden">
                      <div className="flex items-center gap-2 px-3 pt-3">
                        <input type="checkbox" className="h-4 w-4 accent-[var(--g2)]" aria-label={`Select ${t.id}`} checked={selected.has(t.id)} onChange={() => toggleSelect(t.id)} />
                        <span className="mono text-xs text-muted">{t.id}</span>
                        <SeverityChip severity={t.severity} />
                        <span className="ml-auto"><StatusSelect label={`Status for ${t.id}`} value={t.status} onChange={(s) => setStatus([t.id], s)} /></span>
                      </div>
                      <button type="button" aria-expanded={open} onClick={() => setOpenId(open ? null : t.id)} className="block w-full space-y-1.5 px-3 pb-3 pt-2 text-left">
                        {ep && <span className="flex items-start gap-2"><MethodBadge method={ep.method} /><span className="mono break-all text-xs">{ep.url}</span></span>}
                        <span className="flex items-start justify-between gap-2">
                          <span className="text-sm font-medium">{t.title}</span>
                          <ChevronIcon open={open} className="mt-0.5 h-4 w-4 shrink-0 text-faint" />
                        </span>
                        <span className="flex flex-wrap gap-1">
                          <Tag title={t.owasp_api}>{owaspKey(t.owasp_api)}</Tag>
                          {t.cwe.slice(0, 2).map((c) => <Tag key={c}>{c}</Tag>)}
                          <Tag>{t.category}</Tag>
                        </span>
                      </button>
                      <Collapse open={open}>
                        <div className="border-t border-line">
                          <TestCaseDetails tc={t} endpoint={ep} onStatus={setStatus} onNotes={setNotes} />
                        </div>
                      </Collapse>
                    </Card>
                  </li>
                </Fragment>
              );
            })}
          </ul>
        </>
      )}

      {pageCount > 1 && (
        <nav aria-label="Pagination" className="flex items-center justify-center gap-3 pt-1 text-sm">
          <Button size="sm" disabled={cur === 0} onClick={() => setPage(cur - 1)}>Previous</Button>
          <span className="tnum text-muted">Page {cur + 1} of {pageCount}</span>
          <Button size="sm" disabled={cur >= pageCount - 1} onClick={() => setPage(cur + 1)}>Next</Button>
        </nav>
      )}

      {/* Bulk action bar: slides up from the bottom when rows are selected */}
      {selectedCount > 0 && (
        <div role="region" aria-label="Bulk actions" className="overlay fixed bottom-5 left-1/2 z-40 flex max-w-[calc(100vw-1.5rem)] flex-wrap items-center gap-3 px-4 py-2.5" style={{ animation: "slide-up 0.28s cubic-bezier(0.2,0.8,0.2,1) both" }}>
          <span className="tnum text-sm font-semibold"><span className="gradient-text">{selectedCount}</span> selected</span>
          <select
            aria-label="Set status for selected test cases"
            className="input !py-1"
            value=""
            onChange={(e) => {
              if (e.target.value) { setStatus([...selected], e.target.value as Status); setSelected(new Set()); }
            }}
          >
            <option value="">Set status…</option>
            {STATUSES.map((s) => <option key={s}>{s}</option>)}
          </select>
          {selectedCount < filtered.length && (
            <button type="button" className="rounded text-xs text-accent underline underline-offset-2" onClick={() => setSelected(new Set(filtered.map((f) => f.id)))}>Select all {filtered.length} filtered</button>
          )}
          <button type="button" className="rounded text-xs text-muted underline underline-offset-2 hover:text-fg" onClick={() => setSelected(new Set())}>Clear</button>
        </div>
      )}
    </div>
  );
}
