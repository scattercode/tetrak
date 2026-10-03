/**
 * Download the site's webfonts into assets/fonts/ so they can be self-hosted.
 *
 * The site declared four faces and preloaded them, but the files were never
 * vendored -- so every page has been rendering in the local fallbacks (Georgia
 * and the system monospace) rather than the faces the design specifies. This
 * fetches them once; the results are committed and this is not part of the
 * build.
 *
 * A script rather than a manual download because the provenance matters: it
 * records exactly which family, weight and subset each file came from, and
 * re-running it reproduces the same set. All three families are OFL-1.1, and
 * the licence travels with them in assets/fonts/OFL.txt.
 *
 * The `latin` subset only. It covers the site's text; the handful of glyphs
 * outside it (arrows such as → and ↗) are not in these fonts' latin range and
 * fall back to a system face, as they already did.
 *
 * Run:
 *   node scripts/vendor-fonts.mjs
 */

import { writeFileSync, mkdirSync } from "node:fs";
import { join } from "node:path";

const OUT = join(import.meta.dirname, "..", "assets", "fonts");

// The benchmark chart is drawn by matplotlib, which reads TrueType and cannot
// read woff2. Its faces go outside site/ so Hugo never serves them: they are
// build-time input for a committed PNG, not part of the page payload.
const CHART_OUT = join(import.meta.dirname, "..", "..", "tools", "fonts");

// A desktop Chrome UA: the CSS API serves woff2 only to browsers that support
// it, and returns older formats to anything it does not recognise.
const UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36";

const FACES = [
  { file: "playfair-display-700", family: "Playfair Display", spec: "Playfair+Display:wght@700", weight: "700", style: "normal" },
  { file: "source-serif-4-400", family: "Source Serif 4", spec: "Source+Serif+4:ital,wght@0,400", weight: "400", style: "normal" },
  { file: "source-serif-4-600", family: "Source Serif 4", spec: "Source+Serif+4:ital,wght@0,600", weight: "600", style: "normal" },
  { file: "source-serif-4-400-italic", family: "Source Serif 4", spec: "Source+Serif+4:ital,wght@1,400", weight: "400", style: "italic" },
  { file: "ibm-plex-mono-400", family: "IBM Plex Mono", spec: "IBM+Plex+Mono:wght@400", weight: "400", style: "normal" }
];

/** The woff2 URL for the `latin` subset, which the API emits last. */
function latinURL(css) {
  const blocks = css.split("/* latin */");
  if (blocks.length < 2) throw new Error("no /* latin */ block in the CSS response");
  const match = blocks[blocks.length - 1].match(/url\((https:[^)]+\.woff2)\)/);
  if (!match) throw new Error("no woff2 URL in the latin block");
  return match[1];
}

mkdirSync(OUT, { recursive: true });

for (const face of FACES) {
  const cssURL = `https://fonts.googleapis.com/css2?family=${face.spec}&display=swap`;
  const css = await (await fetch(cssURL, { headers: { "User-Agent": UA } })).text();
  const url = latinURL(css);

  const bytes = Buffer.from(await (await fetch(url)).arrayBuffer());
  if (bytes.subarray(0, 4).toString("latin1") !== "wOF2") {
    throw new Error(`${face.file}: not a woff2 file`);
  }
  writeFileSync(join(OUT, `${face.file}.woff2`), bytes);
  console.log(`  ${String(Math.round(bytes.length / 1024)).padStart(3)} KB  ${face.file}.woff2  <- ${face.family} ${face.weight} ${face.style}`);
}

// --- TrueType for the chart -------------------------------------------------
// Firefox 3.5 is the user agent the CSS API answers with TrueType; an IE6 one
// gets Embedded OpenType, which matplotlib cannot read and which fails only at
// render time. The response format is checked below rather than assumed.
const UA_TTF =
  "Mozilla/5.0 (Windows; U; Windows NT 5.1; en-US; rv:1.9.1) Gecko/20090624 Firefox/3.5";
const CHART_FACES = [
  { file: "PlayfairDisplay-Bold", spec: "Playfair+Display:wght@700" },
  { file: "SourceSerif4-Regular", spec: "Source+Serif+4:wght@400" },
  { file: "IBMPlexMono-Regular", spec: "IBM+Plex+Mono:wght@400" }
];

mkdirSync(CHART_OUT, { recursive: true });

for (const face of CHART_FACES) {
  const css = await (await fetch(`https://fonts.googleapis.com/css?family=${face.spec}`, {
    headers: { "User-Agent": UA_TTF }
  })).text();
  const url = css.match(/url\((https:[^)]+)\)/)?.[1];
  if (!url) throw new Error(`${face.file}: no font URL in the CSS response`);

  const bytes = Buffer.from(await (await fetch(url)).arrayBuffer());
  // 0x00010000 or "true" is a TrueType header. An EOT or woff arriving here
  // would break the chart at draw time rather than now.
  const magic = bytes.readUInt32BE(0);
  if (magic !== 0x00010000 && bytes.subarray(0, 4).toString("latin1") !== "true") {
    throw new Error(`${face.file}: not TrueType (magic 0x${magic.toString(16)}) -- check UA_TTF`);
  }
  writeFileSync(join(CHART_OUT, `${face.file}.ttf`), bytes);
  console.log(`  ${String(Math.round(bytes.length / 1024)).padStart(3)} KB  tools/fonts/${face.file}.ttf`);
}

console.log(
  `\n${FACES.length} web faces in assets/fonts/, ${CHART_FACES.length} chart faces in tools/fonts/.\n` +
  "Licence: OFL-1.1 for all three families, see assets/fonts/OFL.txt"
);
