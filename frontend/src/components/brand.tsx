import { useEffect, useRef } from "react";
import { SAFETY_NOTE } from "../types";
import { Button, CloseIcon, LinkedInIcon } from "./ui";

export const AUTHOR = "Hard Pansara";
export const LINKEDIN_URL = "https://www.linkedin.com/in/hard-pansara-22582a288/";

/** Fixed background layer: drifting aurora blobs, a dotted grid with radial fade and a faint noise texture. */
export function Atmosphere() {
  return (
    <div aria-hidden className="atmosphere">
      <i className="blob b1" />
      <i className="blob b2" />
      <i className="blob b3" />
      <div className="grid" />
      <div className="noise" />
    </div>
  );
}

/** Product mark: gradient shield with a check. */
export function Logo({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden>
      <defs>
        <linearGradient id="logo-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#6366f1" /><stop offset=".55" stopColor="#8b5cf6" /><stop offset="1" stopColor="#22d3ee" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="url(#logo-g)" />
      <path d="M32 12l14 5.2V31c0 9-6 15.3-14 18-8-2.7-14-9-14-18V17.2z" fill="none" stroke="#fff" strokeWidth="3.4" strokeLinejoin="round" />
      <path d="m25.5 31.5 4.8 4.8 8.2-9.2" fill="none" stroke="#fff" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Hero graphic: shield inside a radar with a slow scanning sweep (CSS only; static under reduced motion). */
export function RadarShield() {
  return (
    <div className="radar" aria-hidden>
      <div className="ring" /><div className="ring r2" /><div className="ring r3" />
      <div className="sweep" />
      <span className="ping" style={{ left: "70%", top: "28%" }} />
      <span className="ping" style={{ left: "24%", top: "66%", animationDelay: "1.6s" }} />
      <svg viewBox="0 0 64 64" className="absolute left-1/2 top-1/2 h-12 w-12 -translate-x-1/2 -translate-y-1/2">
        <defs>
          <linearGradient id="rs-g" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="var(--g1)" /><stop offset=".55" stopColor="var(--g2)" /><stop offset="1" stopColor="var(--g3)" />
          </linearGradient>
        </defs>
        <path d="M32 8l18 6.6V32c0 11.5-7.7 19.6-18 23-10.3-3.4-18-11.5-18-23V14.6z" fill="color-mix(in srgb, var(--g2) 14%, transparent)" stroke="url(#rs-g)" strokeWidth="3" strokeLinejoin="round" />
        <path d="m23.5 32.5 6.2 6.2 10.8-12" fill="none" stroke="url(#rs-g)" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </div>
  );
}

/** Credit link. `button` variant for the header, `inline` for the footer. Opens LinkedIn in a new tab. */
export function LinkedInLink({ variant = "inline" }: { variant?: "button" | "inline" }) {
  return (
    <a
      href={LINKEDIN_URL}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`Built by ${AUTHOR} — connect on LinkedIn (opens in a new tab)`}
      className={variant === "button" ? "btn btn-ghost btn-sm has-tip" : "has-tip inline-flex items-center gap-1.5 rounded-md font-medium text-fg transition-colors hover:text-accent"}
    >
      <LinkedInIcon className={variant === "button" ? "h-4 w-4 text-[#4f8cff]" : "h-3.5 w-3.5 text-[#4f8cff]"} />
      Built by {AUTHOR}
      <span role="tooltip" className="tip">Connect on LinkedIn</span>
    </a>
  );
}

/** Footer shown on every screen. */
export function Footer({ onAbout }: { onAbout: () => void }) {
  return (
    <footer className="mt-auto border-t border-line px-4 py-4 text-xs text-muted">
      <div className="mx-auto flex w-full max-w-7xl flex-wrap items-center justify-center gap-x-6 gap-y-2 text-center sm:justify-between sm:text-left">
        <p><strong className="font-semibold text-fg">{SAFETY_NOTE}</strong> This tool only analyzes the uploaded file and never sends requests to any target.</p>
        <div className="flex items-center gap-4">
          <LinkedInLink />
          <button type="button" onClick={onAbout} className="rounded-md font-medium underline-offset-2 hover:text-fg hover:underline">About</button>
        </div>
      </div>
    </footer>
  );
}

export function AboutModal({ onClose }: { onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-labelledby="about-title">
      <button type="button" aria-label="Close About" tabIndex={-1} className="fade-in absolute inset-0 bg-black/55 backdrop-blur-sm" onClick={onClose} />
      <div className="overlay pop-in relative w-full max-w-md p-6">
        <button ref={closeRef} type="button" onClick={onClose} aria-label="Close About" className="absolute right-3 top-3 rounded-lg p-1.5 text-muted hover:bg-inset hover:text-fg"><CloseIcon /></button>
        <div className="mb-3 flex items-center gap-3"><Logo className="h-10 w-10" /><h2 id="about-title" className="text-xl font-semibold">About this project</h2></div>
        <p className="text-sm leading-relaxed text-muted">
          API Security Test Planner turns a Postman collection or OpenAPI/Swagger file into a security test plan: test cases mapped to OWASP API Top 10, CWE,
          ASVS and WSTG, plus static findings and an Excel report. It analyzes only the file you upload and never sends a request to any target.
        </p>
        <p className="mt-3 text-sm font-medium">{SAFETY_NOTE}</p>
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <a href={LINKEDIN_URL} target="_blank" rel="noopener noreferrer" className="btn btn-primary">
            <LinkedInIcon className="h-4 w-4" /> Built by {AUTHOR} · Connect on LinkedIn
          </a>
          <Button variant="subtle" onClick={onClose}>Close</Button>
        </div>
      </div>
    </div>
  );
}
