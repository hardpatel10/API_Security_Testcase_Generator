// Image helpers that run inside Playwright pages (canvas), so no image library is needed.
import fs from "node:fs";
import path from "node:path";
import { FINAL, kb, pngSize, rel } from "./lib.mjs";

export const FORMATS = {
  landscape: { w: 1200, h: 627 },
  square: { w: 1080, h: 1080 },
  portrait: { w: 1080, h: 1350 },
};
export const DPR = 2;
export const CREDIT = "Built by Hard Pansara";

/** Pixel statistics used to detect blank / mostly-empty / duplicate images. */
export async function analyzePng(page, buf) {
  return page.evaluate(async (b64) => {
    const img = new Image();
    img.src = `data:image/png;base64,${b64}`;
    await img.decode();
    const draw = (n) => {
      const c = document.createElement("canvas");
      c.width = n; c.height = n;
      const x = c.getContext("2d", { willReadFrequently: true });
      x.drawImage(img, 0, 0, n, n);
      return x.getImageData(0, 0, n, n).data;
    };
    const d = draw(96);
    const n = d.length / 4;
    let sum = 0, sum2 = 0;
    const buckets = new Map();
    for (let i = 0; i < d.length; i += 4) {
      const l = 0.2126 * d[i] + 0.7152 * d[i + 1] + 0.0722 * d[i + 2];
      sum += l; sum2 += l * l;
      const k = ((d[i] >> 4) << 8) | ((d[i + 1] >> 4) << 4) | (d[i + 2] >> 4);
      buckets.set(k, (buckets.get(k) ?? 0) + 1);
    }
    const mean = sum / n;
    const modal = Math.max(...buckets.values()) / n;
    const t = draw(32), thumb = [];
    for (let i = 0; i < t.length; i += 4) thumb.push(Math.round(0.2126 * t[i] + 0.7152 * t[i + 1] + 0.0722 * t[i + 2]));
    return { w: img.naturalWidth, h: img.naturalHeight, std: Math.sqrt(sum2 / n - mean * mean), unique: buckets.size, modal, thumb };
  }, buf.toString("base64"));
}

export const thumbDiff = (a, b) => a.reduce((s, v, i) => s + Math.abs(v - b[i]), 0) / a.length / 255;
/** Largest difference in any single thumbnail cell: a different panel on an otherwise identical page still counts as different. */
export const thumbMaxDiff = (a, b) => Math.max(...a.map((v, i) => Math.abs(v - b[i]))) / 255;

/** Reasons why an image should be rejected ([] when fine). */
export function imageProblems(a, { minUnique = 40, minStd = 6, maxModal = 0.985 } = {}) {
  const p = [];
  if (a.std < minStd) p.push(`looks blank (luminance deviation ${a.std.toFixed(1)})`);
  if (a.unique < minUnique) p.push(`only ${a.unique} distinct colours`);
  if (a.modal > maxModal) p.push(`mostly empty (${(a.modal * 100).toFixed(1)}% one colour)`);
  return p;
}

// ------------------------------------------------------------------------------------------ composition
function backdropCss(theme) {
  return theme === "light"
    ? { bg: "#f1ede6", blobs: ["rgba(99,102,241,.30)", "rgba(168,85,247,.22)", "rgba(34,211,238,.26)"], ink: "#5b5b78", bar: "#e7e3dc", dot: "#cfc9bf", border: "rgba(60,50,130,.18)", shadow: "0 40px 90px -30px rgba(40,30,110,.45)" }
    : { bg: "#07070d", blobs: ["rgba(99,102,241,.42)", "rgba(139,92,246,.30)", "rgba(34,211,238,.20)"], ink: "#9a9ab8", bar: "#16162a", dot: "#34344f", border: "rgba(150,150,255,.28)", shadow: "0 40px 100px -30px rgba(0,0,0,.9)" };
}

export function composeHtml({ b64, iw, ih, W, H, theme }) {
  const t = backdropCss(theme);
  const pad = Math.round(Math.min(W, H) * 0.075);
  const bar = 26;
  const credit = 40;
  const availW = W - 2 * pad;
  const availH = H - 2 * pad - credit + 12 - bar;
  const scale = Math.min(availW / iw, availH / ih, 1.6);
  const fw = Math.round(iw * scale), fh = Math.round(ih * scale);
  const top = Math.round(pad + (H - 2 * pad - credit + 12 - (fh + bar)) / 2);
  const left = Math.round((W - fw) / 2);
  return `<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box;margin:0}
html,body{width:${W}px;height:${H}px;overflow:hidden;background:${t.bg};font-family:Inter,"Segoe UI",system-ui,sans-serif}
.blob{position:absolute;border-radius:50%;filter:blur(${Math.round(Math.min(W, H) * 0.09)}px)}
.b1{width:${W * 0.6}px;height:${W * 0.6}px;left:${-W * 0.15}px;top:${-W * 0.2}px;background:${t.blobs[0]}}
.b2{width:${W * 0.5}px;height:${W * 0.5}px;right:${-W * 0.12}px;top:${H * 0.15}px;background:${t.blobs[1]}}
.b3{width:${W * 0.5}px;height:${W * 0.5}px;left:${W * 0.25}px;bottom:${-W * 0.3}px;background:${t.blobs[2]}}
.frame{position:absolute;left:${left}px;top:${top}px;width:${fw}px;height:${fh + bar}px;border-radius:14px;overflow:hidden;border:1px solid ${t.border};box-shadow:${t.shadow};background:${t.bar}}
.bar{height:${bar}px;display:flex;align-items:center;gap:6px;padding:0 12px;background:${t.bar}}
.bar i{width:9px;height:9px;border-radius:50%;background:${t.dot};display:block}
img{display:block;width:${fw}px;height:${fh}px}
.credit{position:absolute;right:${pad}px;bottom:${Math.round(pad * 0.42)}px;font-size:${Math.max(13, Math.round(W * 0.0125))}px;letter-spacing:.02em;color:${t.ink};font-weight:500}
</style></head><body>
<div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div>
<div class="frame"><div class="bar"><i></i><i></i><i></i></div><img src="data:image/png;base64,${b64}"></div>
<div class="credit">${CREDIT}</div>
</body></html>`;
}

/** Render one LinkedIn-format image (viewport W x H at device scale 2). */
export async function composeFinal(page, { raw, W, H, theme }) {
  const { w, h } = pngSize(raw);
  await page.setViewportSize({ width: W, height: H });
  await page.setContent(composeHtml({ b64: raw.toString("base64"), iw: w / DPR, ih: h / DPR, W, H, theme }));
  await page.evaluate(() => Promise.all([document.fonts.ready, ...[...document.images].map((i) => i.decode())]));
  return page.screenshot({ type: "png" });
}

// ------------------------------------------------------------------------------------------ carousel + contact sheet
export async function writeCarouselPdf(page, pngBuffers, outFile) {
  const uris = [];
  for (const buf of pngBuffers) {
    uris.push(await page.evaluate(async (b64) => {
      const img = new Image();
      img.src = `data:image/png;base64,${b64}`;
      await img.decode();
      const c = document.createElement("canvas");
      c.width = img.naturalWidth; c.height = img.naturalHeight;
      c.getContext("2d").drawImage(img, 0, 0);
      return c.toDataURL("image/jpeg", 0.92); // JPEG keeps the PDF small; text stays sharp at 2x
    }, buf.toString("base64")));
  }
  await page.setContent(`<!doctype html><style>@page{size:1080px 1350px;margin:0}html,body{margin:0;background:#07070d}img{display:block;width:1080px;height:1350px;page-break-after:always}</style>${uris.map((u) => `<img src="${u}">`).join("")}`);
  await page.evaluate(() => Promise.all([...document.images].map((i) => i.decode())));
  await page.pdf({ path: outFile, width: "1080px", height: "1350px", printBackground: true, margin: { top: 0, right: 0, bottom: 0, left: 0 } });
}

export function writeIndexHtml(entries) {
  const groups = Object.keys(FORMATS);
  const section = (fmt) => {
    const items = entries.filter((e) => e.format === fmt);
    return `<h2>${fmt} <small>${FORMATS[fmt].w}×${FORMATS[fmt].h} @2x</small></h2><div class="grid ${fmt}">${items.map((e) =>
      `<figure><img src="${fmt}/${e.file}" alt="${e.file}"><figcaption><b>${e.file}</b><br>${e.px} · ${e.size}</figcaption></figure>`).join("")}</div>`;
  };
  const html = `<!doctype html><html><head><meta charset="utf-8"><title>Final screenshots - contact sheet</title><style>
body{margin:0;padding:32px;background:#0b0b14;color:#d8d8ea;font-family:Inter,"Segoe UI",system-ui,sans-serif}
h1{margin:0 0 4px;font-size:24px}p{margin:0 0 24px;color:#9a9ab8}h2{margin:34px 0 12px;font-size:16px;text-transform:capitalize}h2 small{color:#7a7a98;font-weight:400}
.grid{display:grid;gap:18px}.landscape{grid-template-columns:repeat(4,1fr)}.square{grid-template-columns:repeat(5,1fr)}.portrait{grid-template-columns:repeat(6,1fr)}
figure{margin:0}img{width:100%;display:block;border-radius:8px;border:1px solid #2a2a45}figcaption{font-size:11px;color:#8a8aa8;margin-top:6px;line-height:1.4}
</style></head><body><h1>API Security Test Planner: final screenshots</h1><p>Open the PNGs in screenshots/final/&lt;format&gt;/ · carousel.pdf is ready to upload as a LinkedIn document.</p>${groups.map(section).join("")}</body></html>`;
  fs.writeFileSync(path.join(FINAL, "index.html"), html);
}

export async function writeContactSheet(page) {
  await page.setViewportSize({ width: 1700, height: 900 });
  await page.goto("file:///" + path.join(FINAL, "index.html").replaceAll("\\", "/"));
  await page.evaluate(() => Promise.all([document.fonts.ready, ...[...document.images].map((i) => i.decode().catch(() => {}))]));
  await page.screenshot({ path: path.join(FINAL, "contact-sheet.png"), fullPage: true, scale: "css" });
}

export const describeFile = (f) => `${rel(f)} (${kb(fs.statSync(f).size)})`;
