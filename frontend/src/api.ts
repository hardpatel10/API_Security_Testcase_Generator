import type { Analysis } from "./types";

export const MAX_UPLOAD_BYTES = 4 * 1024 * 1024; // 4 MB across all uploaded files (Vercel body limit is ~4.5 MB)

export class ApiError extends Error {
  status: number;
  code: string;
  hint: string;
  line?: number;
  column?: number;
  /** Present for ENVIRONMENT_ONLY: the environment review that can still be displayed. */
  analysis?: Analysis;
  constructor(message: string, status = 0, code = "ERROR", hint = "") {
    super(message);
    this.status = status;
    this.code = code;
    this.hint = hint;
  }
  /** Plain-text version for the "Copy details" link. */
  details(): string {
    return [
      `code: ${this.code}`,
      `status: ${this.status}`,
      `message: ${this.message}`,
      this.hint && `hint: ${this.hint}`,
      this.line ? `location: line ${this.line}${this.column ? `, column ${this.column}` : ""}` : "",
    ].filter(Boolean).join("\n");
  }
}

interface ErrBody {
  code?: string;
  message?: string;
  hint?: string;
  detail?: unknown;
  line?: number;
  column?: number;
  analysis?: Analysis;
}

function errorFrom(body: ErrBody | null, status: number, fallback: string): ApiError {
  let message = body?.message;
  if (!message && typeof body?.detail === "string") message = body.detail;
  if (!message && Array.isArray(body?.detail) && body!.detail.length) {
    const first = body!.detail[0] as { msg?: string; loc?: unknown[] };
    message = `Invalid request: ${first.loc?.slice(1).join(".") ?? ""} ${first.msg ?? ""}`.trim();
  }
  const e = new ApiError(message ?? fallback, status, body?.code ?? "ERROR", body?.hint ?? "");
  e.line = body?.line;
  e.column = body?.column;
  e.analysis = body?.analysis;
  return e;
}

export interface UploadFiles {
  collection: File | null;
  environment: File | null;
}

/** Upload the collection and/or environment for analysis. XHR gives upload progress. */
export function analyzeFiles(files: UploadFiles, onUploadProgress?: (pct: number) => void): Promise<Analysis> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    if (files.collection) form.append("file", files.collection, files.collection.name);
    if (files.environment) form.append("environment", files.environment, files.environment.name);
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/analyze");
    xhr.responseType = "text";
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onUploadProgress?.(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onerror = () => reject(new ApiError("Could not reach the server.", 0, "NETWORK", "Check your connection and try again."));
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* non-JSON error page */
      }
      if (xhr.status >= 200 && xhr.status < 300 && body) return resolve(body as Analysis);
      reject(errorFrom(body as ErrBody | null, xhr.status, `The server returned an error (HTTP ${xhr.status}).`));
    };
    xhr.send(form);
  });
}

export async function exportReport(
  analysis: Analysis,
  testCaseIds?: string[],
): Promise<{ blob: Blob; filename: string }> {
  let res: Response;
  try {
    res = await fetch("/api/export", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ analysis, test_case_ids: testCaseIds ?? null }),
    });
  } catch {
    throw new ApiError("Could not reach the server. Check your connection and try again.", 0, "NETWORK");
  }
  if (!res.ok) {
    let body: ErrBody | null = null;
    try {
      body = await res.json();
    } catch {
      /* ignore */
    }
    throw errorFrom(
      body,
      res.status,
      res.status === 413
        ? "The report is too large to export in one request. Use 'Export filtered' to export a subset."
        : `Export failed (HTTP ${res.status}).`,
    );
  }
  const cd = res.headers.get("Content-Disposition") ?? "";
  const m = /filename="?([^";]+)"?/.exec(cd);
  return { blob: await res.blob(), filename: m?.[1] ?? "api-security-test-plan.xlsx" };
}

export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export async function fetchSample(name: string): Promise<File> {
  const res = await fetch(`/samples/${name}`);
  if (!res.ok) throw new ApiError("Could not load the sample file.", res.status, "SAMPLE");
  const blob = await res.blob();
  return new File([blob], name, { type: blob.type });
}

export type FileKind = "collection" | "environment" | "unknown";

/** Cheap client-side sniffing so files dropped together can be auto-assigned to the right slot. */
export async function detectKind(file: File): Promise<FileKind> {
  if (/\.ya?ml$/i.test(file.name)) return "collection"; // environments are always JSON
  try {
    const data = JSON.parse(await file.text());
    if (!data || typeof data !== "object" || Array.isArray(data)) return "unknown";
    if (data.info && "item" in data) return "collection";
    if (Array.isArray(data.values) || data._postman_variable_scope === "environment" || data._postman_variable_scope === "globals") return "environment";
    if ("openapi" in data || "swagger" in data) return "collection";
  } catch {
    /* invalid JSON: let the server report the exact syntax error */
  }
  return "unknown";
}

export function formatSize(bytes: number): string {
  return bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
