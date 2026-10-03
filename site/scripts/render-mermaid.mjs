/**
 * Render every ```mermaid block in the content to a committed SVG.
 *
 * The site had a mermaid flowchart in reference/routing.md and nothing to
 * render it, so a reader saw thirty-two lines of `-->` as raw text. The obvious
 * fix -- ship mermaid to the browser -- costs 3.4 MB of JavaScript for one
 * diagram on one page, and the CSP-free, no-CDN, build-time-first shape of this
 * site argues against it.
 *
 * So mermaid runs here instead, at build time, in the Chromium that Playwright
 * already installs. The output is an SVG committed beside the other generated
 * images. The page ships no JavaScript for its diagrams at all.
 *
 * Each SVG is named for a hash of its own source, so the render hook in
 * layouts/_default/_markup/render-codeblock-mermaid.html can find the file for
 * a given block, and an edited diagram produces a new file rather than silently
 * serving the old one.
 *
 * Themed from the design tokens, so a diagram sits on the same paper as the
 * page around it.
 *
 * Run:
 *   node scripts/render-mermaid.mjs          # render anything missing
 *   node scripts/render-mermaid.mjs --check  # fail if anything is missing
 */

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "@playwright/test";

const SITE = join(import.meta.dirname, "..");
const CONTENT = join(SITE, "content");
const OUT = join(SITE, "assets", "images", "diagrams");
const MERMAID = join(SITE, "node_modules", "mermaid", "dist", "mermaid.min.js");

// The light-theme tokens from assets/scss/_tokens.scss. A diagram drawn in
// mermaid's defaults arrives as a purple-and-grey rectangle on a warm paper
// page; these make it belong.
const THEME = {
  background: "#f7f3ec",
  primaryColor: "#efe9df",
  primaryTextColor: "#1e1c19",
  primaryBorderColor: "#b08d4f",
  lineColor: "#6d675e",
  secondaryColor: "#e2dacd",
  tertiaryColor: "#f7f3ec",
  fontFamily: "Source Serif 4, Georgia, serif",
  fontSize: "15px"
};

export function diagramHash(source) {
  return createHash("sha1").update(source.trim()).digest("hex").slice(0, 12);
}

/** Every fenced mermaid block in the content tree. */
function findDiagrams() {
  const walk = dir =>
    readdirSync(dir, { withFileTypes: true }).flatMap(e => {
      const p = join(dir, e.name);
      return e.isDirectory() ? walk(p) : e.name.endsWith(".md") ? [p] : [];
    });

  const found = [];
  for (const file of walk(CONTENT)) {
    const body = readFileSync(file, "utf8");
    for (const m of body.matchAll(/```mermaid\n([\s\S]*?)```/g)) {
      found.push({ file, source: m[1].trim(), hash: diagramHash(m[1]) });
    }
  }
  return found;
}

const diagrams = findDiagrams();
if (!diagrams.length) {
  console.log("render-mermaid: no mermaid blocks in the content");
  process.exit(0);
}

mkdirSync(OUT, { recursive: true });

if (process.argv.includes("--check")) {
  const missing = diagrams.filter(d => !existsSync(join(OUT, `mermaid-${d.hash}.svg`)));
  if (missing.length) {
    console.error(
      `\nrender-mermaid: ${missing.length} diagram(s) have no rendered SVG.\n` +
      "The page would show its source as raw text. Run:  node scripts/render-mermaid.mjs\n\n" +
      missing.map(d => `  ${d.file.slice(CONTENT.length + 1)} (${d.hash})`).join("\n") + "\n"
    );
    process.exit(1);
  }
  console.log(`render-mermaid: ${diagrams.length} diagram(s) rendered`);
  process.exit(0);
}

// Every SVG is named for a hash of its own source, so a diagram whose file
// already exists is by definition current -- there is nothing to redraw. Bail
// before launching Chromium, which is the expensive half of this script and
// was previously paid on every single build.
//
// This is what lets the site build on Cloudflare Pages: the deploy runs
// `npm run build`, prebuild runs this, and the Pages build image has no
// browser and no way to `playwright install --with-deps`. Local renders and
// CI still work exactly as before -- an edited diagram changes its hash, the
// file is missing, and the browser starts.
const missing = diagrams.filter(d => !existsSync(join(OUT, `mermaid-${d.hash}.svg`)));
if (!missing.length) {
  console.log(`render-mermaid: ${diagrams.length} diagram(s) already rendered, nothing to do`);
  process.exit(0);
}

const browser = await chromium.launch();
const page = await browser.newPage();

// The vendored face has to be available *before* mermaid runs. Mermaid sizes
// every node by measuring its label in the browser, so rendering with a
// fallback and then declaring "Source Serif 4" in the SVG produces boxes too
// small for the glyphs that actually arrive -- labels clipped mid-word.
const fontData = readFileSync(join(SITE, "assets", "fonts", "source-serif-4-400.woff2")).toString("base64");
await page.setContent("<!doctype html><meta charset=utf-8><body>");
await page.addStyleTag({
  content:
    `@font-face { font-family: "Source Serif 4"; font-style: normal; font-weight: 400; ` +
    `src: url(data:font/woff2;base64,${fontData}) format("woff2"); }` +
    `body { font-family: "Source Serif 4", Georgia, serif; }`
});
// Runs in the page, not in Node -- document is the browser's.
// eslint-disable-next-line no-undef
await page.evaluate(() => document.fonts.load("15px 'Source Serif 4'").then(() => document.fonts.ready));
await page.addScriptTag({ path: MERMAID });

for (const d of diagrams) {
  const out = join(OUT, `mermaid-${d.hash}.svg`);
  const svg = await page.evaluate(
    async ([source, theme, id]) => {
      // deterministicIds and a fixed handDrawnSeed together make the render
      // reproducible. Without the seed mermaid re-randomises the rough.js
      // bezier control points on every run, so the committed SVG churned by a
      // few hundred bytes each build for no visible change.
      // eslint-disable-next-line no-undef
      window.mermaid.initialize({
        startOnLoad: false,
        theme: "base",
        themeVariables: theme,
        deterministicIds: true,
        deterministicIDSeed: id,
        handDrawnSeed: 1
      });
      // The id is derived from the diagram, not random: mermaid writes it into
      // the SVG root, so a random one rewrites the committed file on every
      // build and produces a diff that means nothing.
      // eslint-disable-next-line no-undef
      const { svg } = await window.mermaid.render("mermaid-" + id, source);
      return svg;
    },
    [d.source, THEME, d.hash]
  );
  writeFileSync(out, svg);
  console.log(`  ${String(Math.round(svg.length / 1024)).padStart(3)} KB  mermaid-${d.hash}.svg  <- ${d.file.slice(CONTENT.length + 1)}`);
}

await browser.close();
console.log(`\n${diagrams.length} diagram(s) rendered into assets/images/diagrams/`);
