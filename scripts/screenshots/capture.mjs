// npm run shots: builds + starts the app, captures the LinkedIn screenshot set from the built-in samples only,
// stops the servers, composes final images, runs quality checks and cleans up tmp/raw leftovers.
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import {
  BASE, FINAL, RAW, ROOT, SAMPLES, TMP, dryRunThenDelete, ensureDir, forbiddenLiterals, kb, listOwned, log, pngSize, rel, scanForSecrets,
  sleep, startServers,
} from "./lib.mjs";
import {
  DPR, FORMATS, analyzePng, composeFinal, imageProblems, thumbDiff, thumbMaxDiff, writeCarouselPdf, writeContactSheet, writeIndexHtml,
} from "./imagetools.mjs";

const results = []; // { id, status: 'ok' | 'skipped' | 'failed', note }
const record = (id, status, note = "") => { results.push({ id, status, note }); log(`  ${status === "ok" ? "✔" : status === "skipped" ? "–" : "✘"} ${id}${note ? `: ${note}` : ""}`); };

// ------------------------------------------------------------------------------------------ browser
async function launchBrowser() {
  const { chromium } = await import("playwright-core");
  const attempts = process.env.SHOTS_BROWSER_PATH
    ? [{ executablePath: process.env.SHOTS_BROWSER_PATH }]
    : [{ channel: "msedge" }, { channel: "chrome" }];
  const errors = [];
  for (const a of attempts) {
    try { return await chromium.launch({ headless: true, ...a }); } catch (e) { errors.push(`${JSON.stringify(a)}: ${String(e.message).split("\n")[0]}`); }
  }
  throw new Error(
    `No browser could be launched.\n  ${errors.join("\n  ")}\n\nOn your machine run ONE of:\n` +
    "  npx playwright-core install chromium     (downloads Playwright's own Chromium)\n" +
    "  set SHOTS_BROWSER_PATH=C:\\path\\to\\chrome.exe   (PowerShell: $env:SHOTS_BROWSER_PATH=...)\n" +
    "then run: npm run shots");
}

// ------------------------------------------------------------------------------------------ demo data (built-in samples only)
async function analyzeSamples() {
  const fd = new FormData();
  fd.append("file", new Blob([fs.readFileSync(path.join(SAMPLES, "sample-postman.json"))]), "sample-postman.json");
  fd.append("environment", new Blob([fs.readFileSync(path.join(SAMPLES, "sample-postman-environment.json"))]), "sample-postman-environment.json");
  const res = await fetch(`${BASE}/api/analyze`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`sample analysis failed (HTTP ${res.status})`);
  return res.json();
}

/** A believable review in progress: a mix of Pass / Fail / N/A / Not Started plus a few notes. */
function buildProgress(analysis) {
  const cycle = ["Pass", "Fail", "Not Started", "Pass", "N/A", "Pass", "Fail", "Not Started", "Pass", "Not Started"];
  const notes = {
    Fail: ["Reproduced on staging. Evidence saved in the shared folder.", "Confirmed by a second tester.", "Missing control; ticket raised with the API team."],
    Pass: ["Verified: request rejected as expected.", "No issue found."],
    "N/A": ["Not applicable: endpoint is public by design."],
  };
  const progress = {};
  analysis.test_cases.forEach((t, i) => {
    const status = cycle[i % cycle.length];
    const list = notes[status];
    progress[t.id] = { status, notes: list && i % 3 === 1 ? list[i % list.length] : "" };
  });
  const high = analysis.test_cases.find((t) => t.severity === "High");
  progress[high.id] = { status: "Fail", notes: "Reproduced on staging: no lockout after 20 failed attempts. Ticket raised." };
  return progress;
}

// ------------------------------------------------------------------------------------------ page helpers
const HIDE_CSS = `
  *::-webkit-scrollbar{display:none!important} html{scrollbar-width:none!important}
  [data-toasts]{display:none!important}
  *{caret-color:transparent!important;cursor:default!important}`;

async function settle(page, { mono = false } = {}) {
  await page.addStyleTag({ content: HIDE_CSS });
  await page.evaluate(() => document.fonts.ready);
  const loaded = await page.evaluate(() => [...document.fonts].filter((f) => f.status === "loaded").map((f) => f.family));
  if (!loaded.some((f) => f.includes("Inter"))) throw new Error("web font Inter did not load (the browser needs internet access for Google Fonts)");
  if (mono && !loaded.some((f) => f.includes("JetBrains"))) throw new Error("web font JetBrains Mono did not load");
  await page.mouse.move(2, 2);
  await page.evaluate(() => { document.activeElement?.blur?.(); window.scrollTo(0, 0); });
  await sleep(900);
}

async function pageProblems(page, { allowLoading = false, literals }) {
  const problems = [];
  const text = await page.evaluate(() => document.body.innerText + "\n" + [...document.querySelectorAll("textarea,input")].map((e) => e.value ?? "").join("\n"));
  problems.push(...scanForSecrets(text, literals).map((h) => `SECRET-LOOKING TEXT (${h})`));
  const dom = await page.evaluate(() => ({
    overflowX: document.documentElement.scrollWidth > window.innerWidth + 1,
    spinners: document.querySelectorAll(".spin, .skeleton, [aria-busy='true']").length,
    chartsLoading: /Loading charts/.test(document.body.innerText),
  }));
  if (dom.overflowX) problems.push("horizontal overflow (text may be cropped)");
  if (!allowLoading && (dom.spinners || dom.chartsLoading)) problems.push("a loading spinner/skeleton is still visible");
  return { problems, text };
}

/** Screenshot with up to 3 attempts. Attempts go to tmp/, the accepted image is copied to raw/. */
async function capture(page, utility, shot, ctx) {
  const name = shot.file;
  for (let attempt = 1; attempt <= 3; attempt++) {
    const tmpFile = path.join(TMP, `${name}.attempt${attempt}.png`);
    const { problems: pp } = await pageProblems(page, { allowLoading: shot.allowLoading, literals: ctx.literals });
    if (pp.some((p) => p.startsWith("SECRET"))) throw new Error(`${name}: ${pp.join("; ")}. Aborting: nothing was saved for this shot.`);
    await page.screenshot({ path: tmpFile, type: "png" });
    const buf = fs.readFileSync(tmpFile);
    const stats = await analyzePng(utility, buf);
    const problems = [...pp, ...imageProblems(stats)];
    if (!problems.length) {
      fs.copyFileSync(tmpFile, path.join(RAW, `${name}.png`));
      return { stats, buf };
    }
    log(`    attempt ${attempt} rejected: ${problems.join("; ")}`);
    await sleep(1500);
  }
  throw new Error(`${name}: could not get a clean capture after 3 attempts`);
}

// ------------------------------------------------------------------------------------------ shots
function defineShots(analysis) {
  const firstTab = (n) => (page) => page.getByRole("tab", { name: new RegExp(`^${n}`) }).click();
  return [
    { id: "01-hero-upload", theme: "dark", vp: [1440, 900], mono: false, expect: "Find API security gaps", run: async () => {} },
    { id: "01-hero-upload", theme: "light", vp: [1440, 900], mono: false, expect: "Find API security gaps", run: async () => {} },
    { id: "02-analysis-loading", theme: "dark", vp: [1440, 900], mono: false, allowLoading: true, expect: "scanning", loading: true },
    { id: "03-overview-dashboard", theme: "dark", vp: [1440, 1120], results: true, expect: "Risk score", mono: false,
      run: async (page) => { await page.waitForSelector("svg.recharts-surface", { timeout: 15000 }); await sleep(600); } },
    { id: "03-overview-dashboard", theme: "light", vp: [1440, 1120], results: true, expect: "Risk score", mono: false,
      run: async (page) => { await page.waitForSelector("svg.recharts-surface", { timeout: 15000 }); await sleep(600); } },
    { id: "04-test-cases-table", theme: "dark", vp: [1440, 1100], results: true, mono: true, filters: { severity: "High" }, expect: "Expected secure result", fit: "tr[data-row]",
      run: async (page) => {
        await firstTab("Test Cases")(page);
        await page.locator("tr[data-row]").first().click();
        await page.getByText("Expected secure result").first().waitFor();
        await sleep(600);
      } },
    { id: "05-endpoint-detail", theme: "dark", vp: [1440, 1000], results: true, mono: true, expect: "Update user", fit: ".space-y-2 > .card",
      run: async (page) => {
        await firstTab("Endpoints")(page);
        await page.locator("[role=option]", { hasText: "Update user" }).locator("button").click();
        await page.getByRole("heading", { name: "Update user" }).waitFor();
        await sleep(500);
      } },
    { id: "06-findings", theme: "dark", vp: [1440, 1050], results: true, mono: true, expect: "Environment findings", fit: "section .space-y-2 > .card",
      run: async (page) => {
        await firstTab("Findings")(page);
        await page.selectOption('select[aria-label="Group"]', "Environment");
        await sleep(400);
        const high = page.locator("button[aria-expanded]").filter({ hasText: "High" });
        await high.nth(0).click();
        await high.nth(1).click();
        await page.getByText("Remediation").first().waitFor();
        await sleep(600);
      } },
    { id: "07-standards", theme: "dark", vp: [1440, 1250], results: true, mono: false, expect: "OWASP API Security Top 10",
      run: async (page) => { await firstTab("Standards")(page); await page.getByText("Test cases mapped to each category").waitFor(); await sleep(600); } },
  ];
}

async function runShot(browser, utility, shot, ctx) {
  const name = shot.theme === "light" ? `${shot.id}-light` : shot.id;
  shot.file = name;
  const seed = { "apitp:theme": shot.theme };
  if (shot.results) {
    seed["apitp:analysis:v1"] = JSON.stringify(ctx.analysis);
    seed["apitp:progress:v1"] = JSON.stringify(ctx.progress);
    seed["apitp:filters:v1"] = JSON.stringify(shot.filters ?? {});
  }
  const context = await browser.newContext({
    viewport: { width: shot.vp[0], height: shot.vp[1] }, deviceScaleFactor: DPR, reducedMotion: "reduce",
    colorScheme: shot.theme, locale: "en-US", timezoneId: "UTC",
  });
  let page;
  try {
    await context.addInitScript((s) => { try { for (const [k, v] of Object.entries(s)) localStorage.setItem(k, v); } catch { /* ignore */ } }, seed);
    if (shot.loading) {
      // Hold the analysis response for a while (the real upload still happens), so the scanning state can be captured mid-progress.
      await context.addInitScript(() => {
        const Orig = window.XMLHttpRequest;
        window.XMLHttpRequest = class extends Orig {
          set onload(fn) { super.onload = fn ? (e) => setTimeout(() => fn.call(this, e), 15000) : fn; }
          get onload() { return super.onload; }
        };
      });
    }
    page = await context.newPage();
    await page.goto(`${BASE}/`);
    if (shot.results) await page.waitForSelector('[role="tab"]');
    else await page.getByRole("button", { name: "Choose file" }).first().waitFor();

    if (shot.loading) {
      await page.setInputFiles("#slot-collection", [path.join(SAMPLES, "sample-postman.json"), path.join(SAMPLES, "sample-postman-environment.json")]);
      await page.getByRole("button", { name: "Analyze", exact: true }).click();
      await page.waitForFunction(() => [...document.querySelectorAll("li.text-fg")].some((li) => li.textContent.trim().startsWith("Generating test cases")), null, { timeout: 25000 })
        .catch(() => log("    (stepper did not reach 'Generating test cases'; capturing the state shown)"));
      await page.getByText("scanning").waitFor();
    } else {
      await shot.run(page);
      if (shot.fit) {
        // end the capture right after the last fully visible row/card instead of cutting one in half
        const bottom = await page.evaluate(([sel, max]) => {
          const b = [...document.querySelectorAll(sel)].map((e) => e.getBoundingClientRect().bottom).filter((v) => v <= max);
          return b.length ? Math.ceil(Math.max(...b)) : null;
        }, [shot.fit, shot.vp[1] - 24]);
        if (bottom) await page.setViewportSize({ width: shot.vp[0], height: bottom + 4 });
      }
    }
    await settle(page, { mono: shot.mono });
    const text = await page.evaluate(() => document.body.innerText);
    if (!text.toLowerCase().includes(shot.expect.toLowerCase())) throw new Error(`${name}: expected screen text "${shot.expect}" was not found; the wrong screen would be captured`);
    const { stats } = await capture(page, utility, shot, ctx);
    ctx.stats[name] = stats;
    record(name, "ok", `${stats.w}x${stats.h}`);
  } catch (e) {
    if (page) await page.screenshot({ path: path.join(TMP, `${name}.attempt0.png`) }).catch(() => {}); // debug image (tmp/ only)
    throw e;
  } finally {
    await context.close();
  }
}

// ------------------------------------------------------------------------------------------ Excel renders
async function renderExcelShots(ctx) {
  const merged = { ...ctx.analysis, test_cases: ctx.analysis.test_cases.map((t) => ({ ...t, ...ctx.progress[t.id] })) };
  const hits = scanForSecrets(JSON.stringify(merged), ctx.literals);
  if (hits.length) throw new Error(`workbook data contains secret-looking text (${hits.join("; ")}). Aborting Excel shots.`);
  const res = await fetch(`${BASE}/api/export`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ analysis: merged, test_case_ids: null }) });
  if (!res.ok) throw new Error(`export failed (HTTP ${res.status})`);
  const xlsx = path.join(TMP, "report.xlsx");
  fs.writeFileSync(xlsx, Buffer.from(await res.arrayBuffer()));

  const have = (cmd) => spawnSync(process.platform === "win32" ? "where" : "which", [cmd], { stdio: "ignore" }).status === 0;
  const outs = { summary: path.join(TMP, "excel-summary.png"), plan: path.join(TMP, "excel-plan.png") };
  let how = null;
  if (have("soffice") && have("pdftoppm")) {
    // LibreOffice -> PDF -> PNG (NOT TESTED on this machine: LibreOffice is not installed here)
    spawnSync("soffice", ["--headless", "--convert-to", "pdf", "--outdir", TMP, xlsx], { stdio: "ignore", timeout: 120000 });
    const pdf = path.join(TMP, "report.pdf");
    if (fs.existsSync(pdf)) {
      const pageWith = (needle) => { for (let p = 1; p <= 40; p++) { const t = spawnSync("pdftotext", ["-f", String(p), "-l", String(p), pdf, "-"], { encoding: "utf8" }); if (t.status !== 0) break; if (t.stdout.includes(needle)) return p; } return null; };
      const planPage = pageWith("Endpoint Test Plan");
      const shoot = (pg, out) => spawnSync("pdftoppm", ["-png", "-r", "170", "-f", String(pg), "-l", String(pg), "-singlefile", pdf, out.replace(/\.png$/, "")], { stdio: "ignore" });
      shoot(1, outs.summary);
      if (planPage) shoot(planPage, outs.plan);
      how = "LibreOffice";
    }
  } else if (process.platform === "win32") {
    const ps = spawnSync("powershell", ["-NoProfile", "-ExecutionPolicy", "Bypass", "-File", path.join(ROOT, "scripts", "screenshots", "render-excel.ps1"), xlsx, TMP],
      { encoding: "utf8", timeout: 180000 });
    if (ps.status === 0 && fs.existsSync(outs.summary)) how = "desktop Excel";
    else log(`    Excel render failed: ${(ps.stderr || ps.stdout || "").trim().split("\n").pop()}`);
  }
  if (!how || !fs.existsSync(outs.summary) || !fs.existsSync(outs.plan)) {
    const why = "no spreadsheet renderer available (needs LibreOffice + pdftoppm, or desktop Excel on Windows)";
    record("08-excel-summary", "skipped", why);
    record("09-excel-test-plan", "skipped", why);
    return;
  }
  for (const [id, src] of [["08-excel-summary", outs.summary], ["09-excel-test-plan", outs.plan]]) {
    const buf = fs.readFileSync(src);
    const stats = await analyzePng(ctx.utility, buf);
    const problems = imageProblems(stats);
    if (problems.length) { record(id, "failed", problems.join("; ")); continue; }
    fs.copyFileSync(src, path.join(RAW, `${id}.png`));
    ctx.stats[id] = stats;
    record(id, "ok", `${stats.w}x${stats.h} via ${how}`);
  }
}

// ------------------------------------------------------------------------------------------ finals
const FINAL_SHOTS = [
  ["01-hero-upload", "dark"], ["01-hero-upload-light", "light"], ["02-analysis-loading", "dark"], ["03-overview-dashboard", "dark"],
  ["03-overview-dashboard-light", "light"], ["04-test-cases-table", "dark"], ["05-endpoint-detail", "dark"], ["06-findings", "dark"],
  ["07-standards", "dark"], ["08-excel-summary", "dark"], ["09-excel-test-plan", "dark"],
];
const CAROUSEL = ["01-hero-upload", "03-overview-dashboard", "04-test-cases-table", "06-findings", "08-excel-summary", "07-standards"];

async function composeAll(browser, utility) {
  const context = await browser.newContext({ viewport: { width: 1200, height: 627 }, deviceScaleFactor: DPR });
  const page = await context.newPage();
  const entries = [];
  const portraitByShot = {};
  for (const [name, theme] of FINAL_SHOTS) {
    const rawFile = path.join(RAW, `${name}.png`);
    if (!fs.existsSync(rawFile)) continue;
    const raw = fs.readFileSync(rawFile);
    for (const [format, { w, h }] of Object.entries(FORMATS)) {
      const png = await composeFinal(page, { raw, W: w, H: h, theme });
      const dir = path.join(FINAL, format);
      ensureDir(dir);
      const file = `${name}.png`;
      fs.writeFileSync(path.join(dir, file), png);
      const { w: pw, h: ph } = pngSize(png);
      entries.push({ format, file, px: `${pw}×${ph}`, size: kb(png.length), bytes: png.length, expected: [w * DPR, h * DPR], actual: [pw, ph], path: path.join(dir, file), name });
      if (format === "portrait") portraitByShot[name] = png;
    }
  }
  const pages = CAROUSEL.filter((n) => portraitByShot[n]);
  if (pages.length) await writeCarouselPdf(page, pages.map((n) => portraitByShot[n]), path.join(FINAL, "carousel.pdf"));
  writeIndexHtml(entries);
  await writeContactSheet(page);
  await context.close();
  return { entries, carouselPages: pages };
}

async function qualityCheck(utility, entries) {
  const failures = [];
  for (const e of entries) {
    const buf = fs.readFileSync(e.path);
    const { w, h } = pngSize(buf);
    const stats = await analyzePng(utility, buf);
    const problems = [];
    if (w !== e.expected[0] || h !== e.expected[1]) problems.push(`dimensions ${w}x${h}, expected ${e.expected.join("x")}`);
    if (buf.length > 5 * 1024 * 1024) problems.push(`file is ${kb(buf.length)} (limit 5 MB)`);
    problems.push(...imageProblems(stats, { minStd: 8, maxModal: 0.9 }));
    if (problems.length) failures.push(`${rel(e.path)}: ${problems.join("; ")}`);
  }
  return failures;
}

// ------------------------------------------------------------------------------------------ main
async function main() {
  for (const d of [RAW, TMP, FINAL]) ensureDir(d);
  const literals = forbiddenLiterals();
  let servers, browser;
  const ctx = { literals, stats: {} };
  try {
    log("1/5 starting servers");
    servers = await startServers();
    log("2/5 launching the browser");
    browser = await launchBrowser();
    const utility = await (await browser.newContext()).newPage();
    ctx.utility = utility;

    log("3/5 preparing demo data from the built-in samples");
    ctx.analysis = await analyzeSamples();
    ctx.progress = buildProgress(ctx.analysis);
    const hits = scanForSecrets(JSON.stringify(ctx.analysis), literals);
    if (hits.length) throw new Error(`analysis output contains secret-looking text: ${hits.join("; ")}`);

    log("4/5 capturing");
    const only = (process.env.SHOTS_ONLY ?? "").split(",").filter(Boolean);
    for (const shot of defineShots(ctx.analysis)) {
      if (only.length && !only.some((o) => shot.id.startsWith(o))) continue;
      const label = shot.theme === "light" ? `${shot.id}-light` : shot.id;
      try { await runShot(browser, utility, shot, ctx); }
      catch (e) {
        if (/SECRET-LOOKING|secret-looking/i.test(e.message)) { servers.stop(); throw e; } // a secret on screen aborts the whole run
        record(label, "failed", e.message.split("\n")[0]);
      }
    }
    await renderExcelShots(ctx).catch((e) => { if (/secret/i.test(e.message)) throw e; record("08-excel-summary", "skipped", e.message); record("09-excel-test-plan", "skipped", e.message); });
    servers.stop();
    servers = null;
    log("• servers stopped");

    log("5/5 composing finals, checking quality, cleaning up");
    // near-identical raw captures (different shots that look the same) are dropped
    const names = Object.keys(ctx.stats);
    for (let i = 0; i < names.length; i++) for (let j = i + 1; j < names.length; j++) {
      const a = ctx.stats[names[i]], b = ctx.stats[names[j]];
      if (a && b && thumbDiff(a.thumb, b.thumb) < 0.01 && thumbMaxDiff(a.thumb, b.thumb) < 0.08) {
        log(`    ${names[j]} is near-identical to ${names[i]}: dropping it`);
        fs.rmSync(path.join(RAW, `${names[j]}.png`), { force: true });
        delete ctx.stats[names[j]];
        record(names[j], "failed", `near-identical to ${names[i]}`);
      }
    }
    // outputs of earlier runs are regenerated: list them first, then remove only files this workflow creates
    dryRunThenDelete(listOwned(FINAL).owned, { label: "final/ (previous outputs, regenerated below)" });
    const { entries, carouselPages } = await composeAll(browser, utility);
    const failures = await qualityCheck(utility, entries);

    // cleanup: stale raw files (not produced by this run) and all of tmp
    const keep = new Set(Object.keys(ctx.stats).map((n) => `${n}.png`));
    const stale = listOwned(RAW).owned.filter((f) => !keep.has(path.basename(f.path)));
    dryRunThenDelete(stale, { label: "raw/ (stale or rejected captures)" });
    const tmpList = listOwned(TMP);
    if (process.env.SHOTS_KEEP_TMP) { log("• SHOTS_KEEP_TMP set: tmp/ kept for debugging"); tmpList.owned.length = 0; }
    dryRunThenDelete(tmpList.owned, { label: "tmp/", removeEmptyDirs: [TMP] });
    if (tmpList.foreign.length) log(`  tmp/ also contains files this workflow did not create; left alone: ${tmpList.foreign.map((f) => rel(f.path)).join(", ")}`);

    // report
    log("\n──────────── REPORT ────────────");
    const ok = results.filter((r) => r.status === "ok"), skipped = results.filter((r) => r.status === "skipped"), failed = results.filter((r) => r.status === "failed");
    log(`captured: ${ok.length}   skipped: ${skipped.length}   failed: ${failed.length}`);
    for (const r of [...skipped, ...failed]) log(`  ${r.status.toUpperCase()} ${r.id}: ${r.note}`);
    log(`final images: ${entries.length}  (${Object.keys(FORMATS).join(", ")})   carousel pages: ${carouselPages.join(", ") || "none"}`);
    log(failures.length ? `QUALITY CHECK FAILED:\n  ${failures.join("\n  ")}` : "quality check: all final images passed (dimensions, not blank, < 5 MB)");
    log(`review: ${rel(path.join(FINAL, "index.html"))}  and  ${rel(path.join(FINAL, "contact-sheet.png"))}`);
    if (failures.length || failed.some((f) => !f.id.startsWith("09") && !f.id.startsWith("08"))) process.exitCode = 1;
  } finally {
    if (servers) servers.stop();
    if (browser) await browser.close().catch(() => {});
  }
}

main().catch((e) => { console.error(`\n✘ ${e.message}`); process.exitCode = 1; }).finally(() => process.exit(process.exitCode ?? 0));
