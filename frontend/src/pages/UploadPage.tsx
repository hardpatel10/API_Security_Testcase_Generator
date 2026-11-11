import { useEffect, useRef, useState, type DragEvent } from "react";
import { analyzeFiles, ApiError, detectKind, fetchSample, formatSize, MAX_UPLOAD_BYTES, type FileKind } from "../api";
import { RadarShield } from "../components/brand";
import {
  AlertIcon, Button, Card, Chip, CheckIcon, CloseIcon, EyeOffIcon, FileIcon, KeyIcon, LayersIcon, LockIcon, UploadIcon, useToast,
} from "../components/ui";
import type { Analysis } from "../types";

const ACCEPT = ".json,.yaml,.yml";

interface Props {
  onAnalyzed: (a: Analysis) => void;
}

type Slot = "collection" | "environment";
interface Problem { title: string; message: string; hint: string; details: string }

const TITLES: Record<string, string> = {
  INVALID_SYNTAX: "The file has a syntax error",
  EMPTY_COLLECTION: "No requests found",
  UNRECOGNIZED_FORMAT: "Unrecognized file format",
  FILE_TOO_LARGE: "Files are too large",
  UNSUPPORTED_VERSION: "Unsupported version",
  TWO_COLLECTIONS: "Two collections uploaded",
  EMPTY_FILE: "The file is empty",
  NETWORK: "Could not reach the server",
};

function problemFrom(e: unknown): Problem {
  if (e instanceof ApiError) {
    return { title: TITLES[e.code] ?? "Could not analyze the files", message: e.message, hint: e.hint, details: e.details() };
  }
  const message = "Something went wrong while analyzing the files.";
  return { title: "Could not analyze the files", message, hint: "Try again, or use a different file.", details: message };
}

/* ---------- 3-step strip: connected line + glowing numbered nodes ---------- */
function Steps() {
  const steps = [
    { n: 1, title: "Upload", text: "Collection + optional environment" },
    { n: 2, title: "Review", text: "Test cases, findings, standards" },
    { n: 3, title: "Export Excel", text: "Report matches the dashboard" },
  ];
  return (
    <ol aria-label="How it works" className="relative mx-auto grid w-full max-w-3xl grid-cols-3">
      <span aria-hidden className="stepper-line absolute left-[16.6%] right-[16.6%] top-4 h-px" />
      {steps.map((s) => (
        <li key={s.n} className="relative flex flex-col items-center px-1 text-center">
          <span className="node-glow tnum flex h-8 w-8 items-center justify-center rounded-full border border-[var(--border-a)] bg-[var(--surface-solid)] text-sm font-bold">
            <span className="gradient-text">{s.n}</span>
          </span>
          <span className="mt-1.5 text-sm font-semibold">{s.title}</span>
          <span className="hidden text-xs text-muted sm:block">{s.text}</span>
        </li>
      ))}
    </ol>
  );
}

/* ---------- Drop zone ---------- */
interface DropSlotProps {
  slot: Slot;
  label: string;
  hint: string;
  file: File | null;
  disabled: boolean;
  onFiles: (files: File[]) => void;
  onRemove: () => void;
}

function DropSlot({ slot, label, hint, file, disabled, onFiles, onRemove }: DropSlotProps) {
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const Icon = slot === "collection" ? FileIcon : KeyIcon;
  const id = `slot-${slot}`;

  function onDrop(e: DragEvent) {
    e.preventDefault();
    setDrag(false);
    if (!disabled && e.dataTransfer.files?.length) onFiles(Array.from(e.dataTransfer.files));
  }

  return (
    <Card
      className={`flex min-h-[10.5rem] flex-col p-4 transition-colors ${file ? "" : "no-border"} ${drag ? "bg-[var(--row-hover)]" : ""}`}
    >
      <div
        onDragOver={(e) => { e.preventDefault(); if (!disabled) setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={onDrop}
        className="absolute inset-0 rounded-[inherit]"
        aria-hidden
      >
        {!file && (
          <svg className="pointer-events-none absolute inset-0 h-full w-full" fill="none">
            <defs>
              <linearGradient id={`dg-${slot}`} x1="0" y1="0" x2="1" y2="1">
                <stop stopColor="var(--g1)" /><stop offset=".5" stopColor="var(--g2)" /><stop offset="1" stopColor="var(--g3)" />
              </linearGradient>
            </defs>
            <rect x="1" y="1" rx="15" ry="15" style={{ width: "calc(100% - 2px)", height: "calc(100% - 2px)", animation: drag ? "dash 0.7s linear infinite" : undefined }}
              stroke={drag ? `url(#dg-${slot})` : "var(--border-strong)"} strokeWidth={drag ? 2.5 : 1.5} strokeDasharray="6 6" />
          </svg>
        )}
      </div>

      <label htmlFor={id} className="relative mb-2 flex items-center gap-2 text-sm font-semibold">
        <span className="flex h-6 w-6 items-center justify-center rounded-md bg-inset text-accent"><Icon className="h-3.5 w-3.5" /></span>
        {label}
      </label>
      {file ? (
        <div className="relative flex flex-1 items-center">
          <div className="pop-in flex w-full items-center gap-3 rounded-xl border border-[var(--border-a)] bg-inset px-3 py-2.5">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-white" style={{ background: "linear-gradient(135deg, var(--btn-1), var(--btn-2))" }}><Icon className="h-4.5 w-4.5" /></span>
            <div className="min-w-0 flex-1 text-left">
              <p className="mono truncate text-[13px] font-medium" title={file.name}>{file.name}</p>
              <p className="tnum text-xs text-muted">{formatSize(file.size)}</p>
            </div>
            <button type="button" onClick={onRemove} disabled={disabled} aria-label={`Remove ${file.name}`}
              className="rounded-lg p-1.5 text-muted transition-colors hover:bg-inset hover:text-fg"><CloseIcon /></button>
          </div>
        </div>
      ) : (
        <div className="relative flex flex-1 flex-col items-center justify-center text-center">
          <UploadIcon className={`mb-1 h-7 w-7 transition-transform ${drag ? "-translate-y-1 text-accent" : "text-faint"}`} />
          <p className="text-sm text-muted">{drag ? "Release to upload" : "Drag & drop here, or"}</p>
          <Button size="sm" className="mt-2" disabled={disabled} onClick={() => input.current?.click()}>Choose file</Button>
          <p className="mt-2 text-xs text-faint">{hint}</p>
        </div>
      )}
      <input id={id} ref={input} type="file" multiple accept={ACCEPT} className="sr-only" disabled={disabled}
        onChange={(e) => { const f = Array.from(e.target.files ?? []); e.target.value = ""; if (f.length) onFiles(f); }} />
    </Card>
  );
}

/* ---------- Loading: progress ring + terminal-style stepper ---------- */
const STAGES = ["Uploading files", "Parsing endpoints", "Applying rules", "Generating test cases", "Mapping standards"];

function AnalyzingCard({ phase, pct }: { phase: "upload" | "analyze"; pct: number }) {
  const [step, setStep] = useState(0);
  useEffect(() => {
    if (phase === "upload") { setStep(0); return; }
    setStep(1);
    const t = setInterval(() => setStep((s) => Math.min(STAGES.length - 1, s + 1)), 700);
    return () => clearInterval(t);
  }, [phase]);
  const overall = phase === "upload" ? Math.round(pct * 0.2) : 20 + Math.round(((step) / (STAGES.length - 1)) * 75);
  const C = 2 * Math.PI * 44;
  return (
    <Card className="rise relative flex min-h-[10.5rem] flex-col items-center gap-5 overflow-hidden p-5 sm:flex-row sm:p-6" >
      <span aria-hidden className="shimmer-bar absolute inset-x-0 top-0 h-[2px] overflow-hidden" style={{ background: "linear-gradient(90deg, var(--g1), var(--g2), var(--g3))" }} />
      <div role="status" aria-live="polite" className="sr-only">{STAGES[step]}</div>
      <div className="relative h-28 w-28 shrink-0">
        <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90" aria-hidden>
          <defs><linearGradient id="ring-g" x1="0" y1="0" x2="1" y2="1"><stop stopColor="var(--g1)" /><stop offset=".55" stopColor="var(--g2)" /><stop offset="1" stopColor="var(--g3)" /></linearGradient></defs>
          <circle cx="50" cy="50" r="44" fill="none" stroke="var(--border)" strokeWidth="6" />
          <circle cx="50" cy="50" r="44" fill="none" stroke="url(#ring-g)" strokeWidth="6" strokeLinecap="round"
            strokeDasharray={C} strokeDashoffset={C * (1 - overall / 100)} style={{ transition: "stroke-dashoffset 0.6s ease" }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center"><span className="tnum gradient-text text-2xl font-bold">{overall}%</span><span className="text-[10px] uppercase tracking-widest text-faint">scanning</span></div>
      </div>
      <ul className="mono w-full max-w-sm space-y-1.5 text-[13px]" aria-hidden>
        {STAGES.map((s, i) => {
          const done = i < step;
          const cur = i === step;
          return (
            <li key={s} className={`flex items-center gap-2.5 ${done ? "text-muted" : cur ? "text-fg" : "text-faint"}`}>
              <span className="flex h-4 w-4 items-center justify-center">
                {done ? <CheckIcon className="h-4 w-4 text-[var(--st-pass)]" /> : cur ? <span className="h-2 w-2 animate-pulse rounded-full" style={{ background: "var(--g2)", boxShadow: "0 0 10px var(--g2)" }} /> : <span className="h-1.5 w-1.5 rounded-full bg-[var(--border-strong)]" />}
              </span>
              <span>{s}{cur ? <span className="text-faint">{phase === "upload" ? ` ${pct}%` : "…"}</span> : null}</span>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

export default function UploadPage({ onAnalyzed }: Props) {
  const toast = useToast();
  const [files, setFiles] = useState<Record<Slot, File | null>>({ collection: null, environment: null });
  const [busy, setBusy] = useState<null | { pct: number; phase: "upload" | "analyze" }>(null);
  const [problem, setProblem] = useState<Problem | null>(null);

  const total = (files.collection?.size ?? 0) + (files.environment?.size ?? 0);
  const canAnalyze = !!(files.collection || files.environment) && !busy;
  const envOnly = !files.collection && !!files.environment;

  /** Validate and route files to the right slot based on their detected type (works for 1 or 2 files at once). */
  async function assign(incoming: File[]) {
    setProblem(null);
    const next = { ...files };
    for (const f of incoming.slice(0, 4)) {
      if (!/\.(json|ya?ml)$/i.test(f.name)) {
        setProblem({ title: "Unsupported file type", message: `"${f.name}" is not a .json, .yaml or .yml file.`,
          hint: "Upload a Postman collection/environment (.json) or an OpenAPI/Swagger file (.json, .yaml, .yml).", details: `unsupported file: ${f.name}` });
        return;
      }
      if (f.size === 0) {
        setProblem({ title: "The file is empty", message: `"${f.name}" has no content.`, hint: "Choose a file that has content.", details: `empty file: ${f.name}` });
        return;
      }
      const kind: FileKind = await detectKind(f);
      const slot: Slot = kind === "environment" ? "environment" : "collection";
      if (kind === "unknown" && next.collection && !next.environment) next.environment = f; // second unknown file: most likely the environment
      else next[slot] = f;
    }
    const sum = (next.collection?.size ?? 0) + (next.environment?.size ?? 0);
    if (sum > MAX_UPLOAD_BYTES) {
      setProblem({
        title: "Files are too large",
        message: `The selected files total ${formatSize(sum)}. The limit is 4 MB for both files combined.`,
        hint: "Remove saved responses/examples from the collection or split it into parts.",
        details: `code: FILE_TOO_LARGE\nsize: ${sum} bytes (limit ${MAX_UPLOAD_BYTES})`,
      });
      return;
    }
    setFiles(next);
  }

  async function analyze() {
    setProblem(null);
    setBusy({ pct: 0, phase: "upload" });
    try {
      const result = await analyzeFiles(files, (pct) => setBusy({ pct, phase: pct >= 100 ? "analyze" : "upload" }));
      setBusy((b) => (b ? { ...b, phase: "analyze" } : b));
      toast(`Analyzed ${result.summary.total_endpoints} endpoints`, "success");
      onAnalyzed(result);
    } catch (e) {
      if (e instanceof ApiError && e.code === "ENVIRONMENT_ONLY" && e.analysis) {
        // Not a failure: show the environment review together with the "no requests" message and hint.
        toast(`Environment review: ${e.analysis.findings.length} finding(s)`, "info");
        onAnalyzed(e.analysis);
      } else {
        setProblem(problemFrom(e));
      }
    } finally {
      setBusy(null);
    }
  }

  async function sample(name: string) {
    try {
      await assign([await fetchSample(name)]);
    } catch (e) {
      setProblem(problemFrom(e));
    }
  }

  async function copyDetails() {
    try {
      await navigator.clipboard.writeText(problem?.details ?? "");
      toast("Error details copied", "info");
    } catch {
      toast("Could not copy to the clipboard", "error");
    }
  }

  return (
    <main className="mx-auto flex w-full max-w-4xl flex-col gap-4 px-4 py-5 sm:py-6">
      <section className="rise flex flex-col items-center text-center">
        <RadarShield />
        <h1 className="mt-3 max-w-3xl text-[1.9rem] font-bold leading-[1.1] sm:text-5xl">
          Find API security gaps <span className="gradient-text">before attackers do</span>
        </h1>
        <p className="mt-2.5 max-w-2xl text-base text-muted">
          Turn a Postman or OpenAPI file into a prioritized, standards-mapped security test plan.
        </p>
        <ul className="mt-3 flex flex-wrap justify-center gap-2" aria-label="Highlights">
          <li><Chip icon={<EyeOffIcon className="h-3.5 w-3.5 text-[var(--g3)]" />}>No requests sent</Chip></li>
          <li><Chip icon={<LockIcon className="h-3.5 w-3.5 text-[var(--g3)]" />}>Runs on your file only</Chip></li>
          <li><Chip icon={<LayersIcon className="h-3.5 w-3.5 text-[var(--g3)]" />}>OWASP · CWE · ASVS · WSTG</Chip></li>
        </ul>
      </section>

      <div className="rise" style={{ animationDelay: "80ms" }}><Steps /></div>

      <section aria-label="Upload files" className="rise flex flex-col gap-3" style={{ animationDelay: "140ms" }}>
        {busy ? (
          <AnalyzingCard phase={busy.phase} pct={busy.pct} />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            <DropSlot slot="collection" label="API collection (required)" hint="Postman v2.1 · OpenAPI 3.x · Swagger 2.0 (.json/.yaml)"
              file={files.collection} disabled={false} onFiles={assign} onRemove={() => setFiles({ ...files, collection: null })} />
            <DropSlot slot="environment" label="Environment file (optional)" hint="Postman environment export (.json) — resolves {{variables}}"
              file={files.environment} disabled={false} onFiles={assign} onRemove={() => setFiles({ ...files, environment: null })} />
          </div>
        )}

        <div className="flex flex-col items-center gap-3">
          <div className="flex flex-wrap items-center justify-center gap-3">
            <Button variant="primary" className="!px-8 !py-2.5 !text-[15px]" disabled={!canAnalyze} loading={!!busy} onClick={analyze}>
              {busy ? "Analyzing…" : envOnly ? "Review environment" : "Analyze"}
            </Button>
            {total > 0 && !busy && <span className="tnum text-xs text-muted">{formatSize(total)} of 4 MB</span>}
          </div>
          {envOnly && !busy && <p className="text-xs text-muted">No collection selected: only the environment will be reviewed.</p>}

          <div className="flex flex-wrap items-center justify-center gap-2">
            <span className="text-sm text-muted">No file handy?</span>
            <button type="button" className="pill" disabled={!!busy} onClick={() => sample("sample-postman.json")}><FileIcon className="h-3.5 w-3.5" /> Postman collection</button>
            <button type="button" className="pill" disabled={!!busy} onClick={() => sample("sample-openapi.yaml")}><FileIcon className="h-3.5 w-3.5" /> OpenAPI spec</button>
            <button type="button" className="pill" disabled={!!busy} onClick={() => sample("sample-postman-environment.json")}><KeyIcon className="h-3.5 w-3.5" /> Environment</button>
          </div>
        </div>
      </section>

      {problem && (
        <div role="alert" className="alert-error rise flex max-h-36 gap-3 overflow-y-auto rounded-xl px-4 py-3 text-sm">
          <AlertIcon className="mt-0.5 h-5 w-5 shrink-0 text-[var(--sev-critical-dot)]" />
          <div className="min-w-0 flex-1">
            <p className="font-semibold">{problem.title}</p>
            <p className="mt-0.5 break-words">{problem.message}</p>
            {problem.hint && <p className="mt-1 break-words text-muted"><span className="font-medium text-fg">Hint:</span> {problem.hint}</p>}
            <button type="button" onClick={copyDetails} className="mt-1.5 rounded text-xs font-medium text-accent underline underline-offset-2">Copy details</button>
          </div>
          <button type="button" onClick={() => setProblem(null)} aria-label="Dismiss error" className="h-fit rounded-md p-1 text-muted hover:bg-inset hover:text-fg"><CloseIcon /></button>
        </div>
      )}
    </main>
  );
}
