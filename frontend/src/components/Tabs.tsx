import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";

interface Props<T extends string> {
  tabs: readonly T[];
  value: T;
  onChange: (t: T) => void;
  label: string;
  counts?: Partial<Record<T, number>>;
}

/** Pill tab bar with a sliding, animated active indicator. Arrow keys move between tabs. */
export default function Tabs<T extends string>({ tabs, value, onChange, label, counts }: Props<T>) {
  const wrap = useRef<HTMLDivElement>(null);
  const btns = useRef<Record<string, HTMLButtonElement | null>>({});
  const [box, setBox] = useState<{ x: number; w: number } | null>(null);

  const measure = () => {
    const b = btns.current[value];
    if (b) setBox({ x: b.offsetLeft, w: b.offsetWidth });
  };
  useLayoutEffect(measure, [value, tabs, counts]);
  useEffect(() => {
    const ro = new ResizeObserver(measure);
    if (wrap.current) ro.observe(wrap.current);
    window.addEventListener("resize", measure);
    return () => { ro.disconnect(); window.removeEventListener("resize", measure); };
  });
  useEffect(() => { btns.current[value]?.scrollIntoView({ block: "nearest", inline: "nearest" }); }, [value]);

  function onKey(e: KeyboardEvent<HTMLDivElement>) {
    const i = tabs.indexOf(value);
    let n = i;
    if (e.key === "ArrowRight") n = (i + 1) % tabs.length;
    else if (e.key === "ArrowLeft") n = (i + tabs.length - 1) % tabs.length;
    else if (e.key === "Home") n = 0;
    else if (e.key === "End") n = tabs.length - 1;
    else return;
    e.preventDefault();
    onChange(tabs[n]);
    requestAnimationFrame(() => btns.current[tabs[n]]?.focus());
  }

  return (
    <div
      ref={wrap}
      role="tablist"
      aria-label={label}
      onKeyDown={onKey}
      className="relative flex max-w-full gap-0.5 overflow-x-auto rounded-xl border border-line bg-inset p-1 [scrollbar-width:none]"
    >
      {box && (
        <span
          aria-hidden
          className="pointer-events-none absolute bottom-1 top-1 rounded-lg transition-[transform,width] duration-300 ease-[cubic-bezier(0.3,0.9,0.3,1)]"
          style={{
            width: box.w, transform: `translateX(${box.x}px)`,
            background: "color-mix(in srgb, var(--g1) 16%, transparent)", border: "1px solid var(--border-a)",
            boxShadow: "0 0 18px -6px var(--glow), inset 0 -2px 0 0 var(--g2)",
          }}
        />
      )}
      {tabs.map((t) => (
        <button
          key={t}
          ref={(el) => { btns.current[t] = el; }}
          role="tab"
          aria-selected={value === t}
          tabIndex={value === t ? 0 : -1}
          onClick={() => onChange(t)}
          className={`relative z-10 flex items-center gap-1.5 whitespace-nowrap rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors ${value === t ? "text-fg" : "text-muted hover:text-fg"}`}
        >
          {t}
          {counts?.[t] !== undefined && <span className="tnum rounded-full bg-inset px-1.5 text-[11px] text-muted">{counts[t]}</span>}
        </button>
      ))}
    </div>
  );
}
