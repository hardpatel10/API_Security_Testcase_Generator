import { useEffect, useMemo, useRef, useState } from "react";
import type { Endpoint } from "../types";
import { MethodBadge, SearchIcon } from "./ui";

interface Props {
  endpoints: Endpoint[];
  tabs: readonly string[];
  onClose: () => void;
  onEndpoint: (id: string) => void;
  onTab: (tab: string) => void;
}

type Item = { kind: "tab"; key: string; label: string } | { kind: "ep"; key: string; ep: Endpoint };

/** Ctrl/Cmd+K quick jump: go to a tab or straight to an endpoint. */
export default function CommandPalette({ endpoints, tabs, onClose, onEndpoint, onTab }: Props) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);

  const items: Item[] = useMemo(() => {
    const s = q.trim().toLowerCase();
    const t: Item[] = tabs.filter((x) => !s || x.toLowerCase().includes(s)).map((x) => ({ kind: "tab", key: `tab-${x}`, label: x }));
    const e: Item[] = endpoints
      .filter((x) => !s || `${x.id} ${x.name} ${x.method} ${x.url}`.toLowerCase().includes(s))
      .slice(0, 40).map((x) => ({ kind: "ep", key: x.id, ep: x }));
    return [...t, ...e];
  }, [q, endpoints, tabs]);

  useEffect(() => { input.current?.focus(); }, []);
  useEffect(() => setActive(0), [q]);
  useEffect(() => { list.current?.querySelector<HTMLElement>('[aria-selected="true"]')?.scrollIntoView({ block: "nearest" }); }, [active]);

  function choose(it: Item | undefined) {
    if (!it) return;
    if (it.kind === "tab") onTab(it.label); else onEndpoint(it.ep.id);
    onClose();
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-start justify-center p-4 pt-[12vh]" role="dialog" aria-modal="true" aria-label="Quick jump">
      <button type="button" aria-label="Close quick jump" tabIndex={-1} className="fade-in absolute inset-0 bg-black/55 backdrop-blur-sm" onClick={onClose} />
      <div className="overlay pop-in relative w-full max-w-xl overflow-hidden">
        <div className="flex items-center gap-2 border-b border-line px-4 transition-shadow focus-within:shadow-[inset_0_-2px_0_var(--g1)]">
          <SearchIcon className="h-4 w-4 text-faint" />
          <input
            ref={input}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Jump to endpoint or section"
            aria-controls="palette-list"
            placeholder="Jump to an endpoint or section…"
            className="w-full rounded-none bg-transparent py-3.5 text-sm text-fg placeholder:text-faint focus-visible:!shadow-none focus-visible:!outline-none"
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(items.length - 1, a + 1)); }
              else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
              else if (e.key === "Enter") { e.preventDefault(); choose(items[active]); }
              else if (e.key === "Escape") onClose();
            }}
          />
          <kbd className="tag">Esc</kbd>
        </div>
        <ul id="palette-list" ref={list} role="listbox" className="max-h-[50vh] overflow-y-auto p-2">
          {items.length === 0 && <li className="px-3 py-6 text-center text-sm text-muted">Nothing matches “{q}”.</li>}
          {items.map((it, i) => (
            <li key={it.key} role="option" aria-selected={i === active}>
              <button
                type="button"
                tabIndex={-1}
                onMouseMove={() => setActive(i)}
                onClick={() => choose(it)}
                className={`flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm ${i === active ? "bg-[var(--row-hover)] shadow-[inset_3px_0_0_var(--g1)]" : ""}`}
              >
                {it.kind === "tab" ? (
                  <><span className="tag">Go to</span><span className="font-medium">{it.label}</span></>
                ) : (
                  <><MethodBadge method={it.ep.method} /><span className="min-w-0 flex-1"><span className="block truncate font-medium">{it.ep.name}</span><span className="mono block truncate text-[11px] text-muted">{it.ep.url}</span></span><span className="mono text-[11px] text-faint">{it.ep.id}</span></>
                )}
              </button>
            </li>
          ))}
        </ul>
        <div className="flex items-center gap-3 border-t border-line px-4 py-2 text-[11px] text-faint">
          <span><kbd className="tag">↑↓</kbd> navigate</span><span><kbd className="tag">Enter</kbd> open</span><span className="ml-auto"><kbd className="tag">Ctrl/⌘ K</kbd></span>
        </div>
      </div>
    </div>
  );
}
