import {
  createContext, useCallback, useContext, useMemo, useRef, useState,
  type ButtonHTMLAttributes, type CSSProperties, type ReactNode,
} from "react";
import { STATUSES, type Status } from "../types";

/* =====================================================================================================
   Design-system primitives. All colour comes from CSS tokens in index.css.
   ===================================================================================================== */

/* ---------- Icons (inline SVG, no icon library) ---------- */
type IconProps = { className?: string };
const base = (p: IconProps) => ({
  className: p.className ?? "h-4 w-4",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.9,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  viewBox: "0 0 24 24",
  "aria-hidden": true,
});
export const SunIcon = (p: IconProps) => (
  <svg {...base(p)}><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></svg>
);
export const MoonIcon = (p: IconProps) => (
  <svg {...base(p)}><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" /></svg>
);
export const DownloadIcon = (p: IconProps) => (
  <svg {...base(p)}><path d="M12 3v12m0 0 4-4m-4 4-4-4M4 21h16" /></svg>
);
export const UploadIcon = (p: IconProps) => (
  <svg {...base(p)}><path d="M12 16V4m0 0 4 4m-4-4-4 4M4 20h16" /></svg>
);
export const CopyIcon = (p: IconProps) => (
  <svg {...base(p)}><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 0 1 2-2h9" /></svg>
);
export const ChevronIcon = ({ open, className }: { open?: boolean; className?: string }) => (
  <svg {...base({ className: `${className ?? "h-4 w-4"} transition-transform duration-200 ${open ? "rotate-90" : ""}` })}><path d="m9 6 6 6-6 6" /></svg>
);
export const ShieldIcon = (p: IconProps) => (
  <svg {...base(p)}><path d="M12 3l8 3v6c0 5-3.4 8.7-8 10-4.6-1.3-8-5-8-10V6z" /><path d="m9 12 2 2 4-4" /></svg>
);
export const ResetIcon = (p: IconProps) => (
  <svg {...base(p)}><path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" /></svg>
);
export const SpinnerIcon = (p: IconProps) => (
  <svg {...base({ className: `${p.className ?? "h-4 w-4"} spin` })}><path d="M21 12a9 9 0 1 1-6.2-8.6" /></svg>
);
export const FileIcon = (p: IconProps) => (
  <svg {...base(p)}><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" /><path d="M14 3v5h5M9 13h6M9 17h4" /></svg>
);
export const ExternalIcon = (p: IconProps) => (
  <svg {...base({ className: p.className ?? "h-3 w-3" })}><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" /></svg>
);
export const SearchIcon = (p: IconProps) => (
  <svg {...base(p)}><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
);
export const FilterIcon = (p: IconProps) => (
  <svg {...base(p)}><path d="M3 5h18M6 12h12M10 19h4" /></svg>
);
export const CloseIcon = (p: IconProps) => (
  <svg {...base(p)}><path d="M6 6l12 12M18 6 6 18" /></svg>
);
export const AlertIcon = (p: IconProps) => (
  <svg {...base(p)}><circle cx="12" cy="12" r="9" /><path d="M12 8v5M12 16.5v.01" /></svg>
);
export const CheckIcon = (p: IconProps) => (
  <svg {...base(p)}><circle cx="12" cy="12" r="9" /><path d="m8.5 12.5 2.5 2.5 4.5-5" /></svg>
);
export const InfoIcon = (p: IconProps) => (
  <svg {...base(p)}><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 7.6v.01" /></svg>
);
export const KeyIcon = (p: IconProps) => (
  <svg {...base(p)}><circle cx="8" cy="15" r="4" /><path d="m11 12 9-9M16 7l3 3" /></svg>
);
export const LockIcon = (p: IconProps) => (
  <svg {...base(p)}><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg>
);
export const EyeOffIcon = (p: IconProps) => (
  <svg {...base(p)}><path d="M3 3l18 18M10.6 6.2A9.8 9.8 0 0 1 12 6c5 0 8.5 4 9.5 6-.4.8-1.3 2.2-2.7 3.4M6.5 7.8C4.4 9.2 3 11.2 2.5 12c1 2 4.5 6 9.5 6 1.4 0 2.6-.3 3.7-.8M9.9 9.9a3 3 0 0 0 4.2 4.2" /></svg>
);
export const LayersIcon = (p: IconProps) => (
  <svg {...base(p)}><path d="m12 3 9 5-9 5-9-5z" /><path d="m3 13 9 5 9-5" /></svg>
);
export const TerminalIcon = (p: IconProps) => (
  <svg {...base(p)}><rect x="3" y="4" width="18" height="16" rx="3" /><path d="m7 10 3 2-3 2M13 15h4" /></svg>
);
export const CommandIcon = (p: IconProps) => (
  <svg {...base(p)}><path d="M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z" /></svg>
);
export const LinkedInIcon = ({ className }: IconProps) => (
  <svg className={className ?? "h-4 w-4"} viewBox="0 0 24 24" fill="currentColor" aria-hidden>
    <path d="M20.4 2H3.6C2.7 2 2 2.7 2 3.6v16.8c0 .9.7 1.6 1.6 1.6h16.8c.9 0 1.6-.7 1.6-1.6V3.6c0-.9-.7-1.6-1.6-1.6zM8 19H5V9.5h3V19zM6.5 8.2a1.7 1.7 0 110-3.4 1.7 1.7 0 010 3.4zM19 19h-3v-4.6c0-1.1 0-2.5-1.5-2.5s-1.8 1.2-1.8 2.4V19h-3V9.5h2.9v1.3c.4-.8 1.4-1.5 2.8-1.5 3 0 3.6 2 3.6 4.6V19z" />
  </svg>
);

/* ---------- Button / Card ---------- */
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "ghost" | "subtle";
  size?: "md" | "sm";
  loading?: boolean;
}
export function Button({ variant = "ghost", size = "md", loading, className = "", children, disabled, ...rest }: ButtonProps) {
  return (
    <button
      type="button"
      {...rest}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={`btn btn-${variant} ${size === "sm" ? "btn-sm" : ""} ${loading ? "is-loading" : ""} ${className}`}
    >
      {children}
    </button>
  );
}

export function Card({ className = "", children, style }: { className?: string; children: ReactNode; style?: CSSProperties }) {
  return <div className={`card ${className}`} style={style}>{children}</div>;
}

/* ---------- Badges, chips, tags ---------- */
export function MethodBadge({ method }: { method: string }) {
  const known = ["GET", "POST", "PUT", "PATCH", "DELETE"].includes(method);
  return <span className={`method ${known ? `m-${method.toLowerCase()}` : "m-other"}`}>{method}</span>;
}

/** Severity chip: glowing dot + text (colour is never the only signal). */
export function SeverityChip({ severity }: { severity: string }) {
  return (
    <span className={`chip sev-${severity.toLowerCase()}`}>
      <span className="dot" aria-hidden />
      {severity}
    </span>
  );
}

/** Small outlined standards badge (OWASP / CWE / ASVS / WSTG). */
export function Tag({ children, title, href }: { children: ReactNode; title?: string; href?: string }) {
  return href ? (
    <a href={href} target="_blank" rel="noopener noreferrer" title={title} className="tag">{children}</a>
  ) : (
    <span className="tag" title={title}>{children}</span>
  );
}

/** A generic outlined pill chip. */
export function Chip({ children, icon, className = "" }: { children: ReactNode; icon?: ReactNode; className?: string }) {
  return <span className={`pill ${className}`}>{icon}{children}</span>;
}

const STATUS_CLASS: Record<Status, string> = { "Not Started": "st-notstarted", Pass: "st-pass", Fail: "st-fail", "N/A": "st-na" };
export function StatusSelect({ value, onChange, label }: { value: Status; onChange: (s: Status) => void; label: string }) {
  return (
    <span className={`status-wrap ${STATUS_CLASS[value]}`}>
      <span className="dot" aria-hidden />
      <select
        aria-label={label}
        value={value}
        onChange={(e) => onChange(e.target.value as Status)}
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
        className="input !py-1"
      >
        {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
    </span>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`skeleton ${className}`} />;
}

/* ---------- Line-art illustrations (empty / error / 404 states) ---------- */
export type ArtKind = "search" | "upload" | "clean" | "lost" | "error";
export function LineArt({ kind }: { kind: ArtKind }) {
  const gid = `la-${kind}`;
  return (
    <svg viewBox="0 0 96 96" className="h-24 w-24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <defs>
        <linearGradient id={gid} x1="8" y1="8" x2="88" y2="88">
          <stop stopColor="var(--g1)" /><stop offset=".55" stopColor="var(--g2)" /><stop offset="1" stopColor="var(--g3)" />
        </linearGradient>
      </defs>
      <g stroke={`url(#${gid})`}>
        <circle cx="48" cy="48" r="38" strokeDasharray="2 6" opacity=".55" />
        {kind === "search" && <><circle cx="42" cy="42" r="16" /><path d="m54 54 14 14" /><path d="M35 42h14M42 35v14" opacity=".6" /></>}
        {kind === "upload" && <><rect x="26" y="52" width="44" height="16" rx="5" /><path d="M48 46V24m0 0-9 9m9-9 9 9" /></>}
        {kind === "clean" && <><path d="M48 22l20 8v14c0 14-8.5 22-20 26-11.5-4-20-12-20-26V30z" /><path d="m39 46 7 7 13-14" /></>}
        {kind === "lost" && <><circle cx="48" cy="48" r="22" /><path d="m39 39 18 18M57 39 39 57" /><path d="M48 14v8M48 74v8M14 48h8M74 48h8" opacity=".6" /></>}
        {kind === "error" && <><path d="M48 24 74 68H22z" /><path d="M48 42v14M48 62v.5" /></>}
      </g>
    </svg>
  );
}

export function EmptyState({ title, hint, action, art = "search" }: { title: string; hint?: string; action?: ReactNode; art?: ArtKind }) {
  return (
    <Card className="rise flex flex-col items-center gap-2 px-6 py-12 text-center">
      <LineArt kind={art} />
      <p className="text-lg font-semibold">{title}</p>
      {hint && <p className="max-w-md text-sm text-muted">{hint}</p>}
      {action && <div className="mt-2">{action}</div>}
    </Card>
  );
}

/* ---------- Toasts: slide in with icon and a draining progress bar ---------- */
type ToastKind = "success" | "error" | "info";
interface ToastItem { id: number; kind: ToastKind; text: string; ms: number }
const ToastCtx = createContext<(text: string, kind?: ToastKind) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const next = useRef(1);
  const push = useCallback((text: string, kind: ToastKind = "info") => {
    const id = next.current++;
    const ms = kind === "error" ? 6000 : 3200;
    setItems((l) => [...l.slice(-3), { id, kind, text, ms }]);
    setTimeout(() => setItems((l) => l.filter((t) => t.id !== id)), ms);
  }, []);
  const value = useMemo(() => push, [push]);
  const tone: Record<ToastKind, { icon: ReactNode; color: string }> = {
    success: { icon: <CheckIcon className="h-5 w-5" />, color: "var(--st-pass)" },
    error: { icon: <AlertIcon className="h-5 w-5" />, color: "var(--st-fail)" },
    info: { icon: <InfoIcon className="h-5 w-5" />, color: "var(--g1)" },
  };
  return (
    <ToastCtx.Provider value={value}>
      {children}
      <div data-toasts className="pointer-events-none fixed bottom-4 right-4 z-[70] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2" role="status" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} className="overlay pointer-events-auto relative flex items-start gap-3 overflow-hidden px-4 py-3 text-sm" style={{ animation: "toast-in 0.28s cubic-bezier(0.2,0.8,0.2,1) both" }}>
            <span style={{ color: tone[t.kind].color }}>{tone[t.kind].icon}</span>
            <span className="flex-1">{t.text}</span>
            <span aria-hidden className="absolute bottom-0 left-0 h-[3px] w-full origin-left"
              style={{ background: tone[t.kind].color, animation: `toast-bar ${t.ms}ms linear forwards` }} />
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
