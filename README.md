# API Security Test Planner

> Built by [Hard Pansara](https://www.linkedin.com/in/hard-pansara-22582a288/) · [Connect on LinkedIn](https://www.linkedin.com/in/hard-pansara-22582a288/)

Upload a Postman Collection v2.1 or an OpenAPI 3.x / Swagger 2.0 file (JSON or YAML). The app parses every
endpoint, generates security test cases per endpoint (mapped to OWASP API Top 10 2023, CWE, ASVS 4.0, WSTG),
flags misconfigurations found **in the file itself** (static analysis), shows it all on a dashboard and exports an
Excel report that matches the website (including the Status and Notes you set).

> **Perform tests only on systems you are authorized to assess.** The tool never sends requests to any target.

## Layout

```
api/index.py        Vercel entrypoint (exposes `app`)
backend/            models.py, standards.py, parsers/, rules/, generator/, export/, app/main.py, tests/
frontend/           React + Vite + TypeScript + Tailwind (src/components, src/pages, src/api.ts, src/types.ts)
frontend/public/samples/   sample-postman.json, sample-openapi.yaml (served statically, not in the function bundle)
vercel.json, requirements.txt (runtime only), requirements-dev.txt, .python-version
```

## Local setup

```bash
python -m venv .venv
.venv/Scripts/activate            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
cd frontend && npm install && cd ..
```

Run (two terminals):

```bash
uvicorn backend.app.main:app --reload --port 8000     # API
cd frontend && npm run dev                            # UI on http://localhost:5173 (proxies /api -> :8000)
```

Tests: `pytest` (parsers, format detection, 12 endpoint rules + environment rules, generator, Excel export, API).
Frontend type-check + build: `cd frontend && npm run build`.

## Deploy on Vercel

1. Push the repo to GitHub and import it in Vercel (no framework preset needed; `vercel.json` sets the commands).
2. Vercel builds the UI with Vite (`frontend/dist`) and runs `api/index.py` as a Python function
   (Python 3.12 pinned by `.python-version`; deps from `requirements.txt`).
3. `/api/*` is rewritten to the function, so UI and API share one domain (no CORS).

Or with the CLI: `npm i -g vercel && vercel --prod`.

### Limits and design notes

- Stateless: nothing is written to disk. Uploads are stream-parsed into memory (Starlette's form parser would spill
  files >1 MB to a temp file, so a small in-memory multipart reader is used instead); the workbook is built in `io.BytesIO`.
- Vercel's request/response limit is ~4.5 MB. Uploads over **4 MB** are rejected in the UI and with HTTP 413 by the API.
  `/api/export` receives the full analysis JSON, so very large collections may exceed the limit on export.
- Secrets found in the file are masked (`eyJh****`) in the parser; raw values are never returned or exported.
- Injection / input-validation tests are mapped to API10:2023; other mappings are listed in `backend/standards.py`
  (a unit test verifies every referenced CWE/ASVS/WSTG ID exists in the catalog).
- The Excel "Endpoint Test Plan" sheet adds `Test ID` and `Category` columns to your specified ones so the Summary
  can COUNTIF by category and rows can be matched to the website.
- Summary counts are COUNTIF formulas; Excel calculates them when the file is opened.

## Postman environment files

Upload an environment export next to the collection (second slot, optional). `{{variables}}` in URLs, headers and bodies
are resolved from it; placeholder values such as `<lawyer password>` are never substituted, and secret-looking values are
substituted only in masked form. The environment is also reviewed (plain-HTTP URLs, secrets stored as type `default`,
service-role/admin/root keys, real-looking secret values) and reported as **Environment** findings (own group in the
Findings tab, own `Environment Findings` Excel sheet). Uploading an environment alone runs only that review.

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | liveness |
| POST | `/api/analyze` | multipart `file` (collection) + optional `environment` -> `{collection, endpoints, findings, test_cases, summary, environment, notice}`. Errors are JSON `{code, message, hint}`: 422 `INVALID_SYNTAX` (with `line`/`column`), `EMPTY_COLLECTION`, `UNRECOGNIZED_FORMAT`, `ENVIRONMENT_ONLY` (also carries the environment review as `analysis`), 413 `FILE_TOO_LARGE` (4 MB for both files combined) |
| POST | `/api/export` | `{analysis, test_case_ids?}` -> `.xlsx` (omit ids for all) |

## Design system

One token-based design system (`frontend/src/index.css`: surfaces, accent gradient, severity/method/status palettes, glass cards, motion) is shared by every screen through
`components/ui.tsx` (Button, Card, badges, chips, status select, EmptyState, Toast, Skeleton), `components/brand.tsx` (logo, radar hero, footer, About),
`Tabs.tsx`, `DataTable.tsx`, `CommandPalette.tsx` and `motion.tsx`. Dark is the default theme (saved in `localStorage`); `prefers-reduced-motion` disables all motion.
Keyboard: `/` focuses test-case search, `Ctrl/Cmd+K` opens quick jump, arrow keys/Enter/Space work in the table, arrow keys switch tabs.

## Sample files

(Credit: the Excel report's Summary sheet also carries a "Built by Hard Pansara" footer link.)

`frontend/public/samples/`: `sample-postman.json`, `sample-openapi.yaml`, `sample-postman-environment.json` (also buttons on the upload screen).
