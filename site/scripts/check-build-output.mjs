/**
 * Fail the build if the output carries development URLs.
 *
 * `hugo server` rewrites baseURL to localhost, and it used to write into
 * public/ as it did so. Running it after the build -- which is what the Pages
 * workflow did, because Playwright starts a server -- replaced every absolute
 * URL in the artefact with http://localhost:1313. The site still looked fine:
 * pages are served by relative paths, so the only visible casualties were the
 * nine alias pages, which redirected visitors to their own machine.
 *
 * `npm run start` now renders to memory and the workflow builds last, so this
 * should never trigger. It exists because nothing else would have caught it:
 * the build succeeded, the tests passed, and the broken redirect only shows up
 * to somebody following an old link.
 *
 * Runs automatically as `postbuild`.
 */

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const PUBLIC = join(import.meta.dirname, "..", "public");
const FORBIDDEN = /https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?/g;

function walk(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return walk(path);
    return /\.(html|json|xml|css|js)$/.test(entry.name) ? [path] : [];
  });
}

const offenders = [];
for (const file of walk(PUBLIC)) {
  const matches = readFileSync(file, "utf8").match(FORBIDDEN);
  if (matches) {
    offenders.push(`${file.slice(PUBLIC.length + 1)} (${matches.length}× ${matches[0]})`);
  }
}

if (offenders.length) {
  console.error(
    `\ncheck-build-output: ${offenders.length} file(s) in public/ contain a development URL.\n` +
    "This output must not be published — it would send visitors to their own machine.\n" +
    "A server has almost certainly written over the build; rebuild with the server stopped.\n\n" +
    offenders.slice(0, 20).map(o => `  ${o}`).join("\n") +
    (offenders.length > 20 ? `\n  … and ${offenders.length - 20} more` : "") + "\n"
  );
  process.exit(1);
}

// Every font the stylesheet asks for must actually be in the build. Hugo only
// publishes an asset something requests, so preloading a subset of the faces
// silently dropped three files while @font-face went on referencing all five --
// a 404 per face, and the page quietly rendering in its fallback stack.
const missingFonts = [];
for (const css of walk(PUBLIC).filter(f => f.endsWith(".css"))) {
  const body = readFileSync(css, "utf8");
  for (const m of body.matchAll(/url\(["']?([^"')]+\.woff2?)["']?\)/g)) {
    const ref = m[1].replace(/^\.\.\//, "");
    if (!existsSync(join(PUBLIC, ref))) missingFonts.push(`${css.slice(PUBLIC.length + 1)} -> ${ref}`);
  }
}

if (missingFonts.length) {
  console.error(
    `\ncheck-build-output: ${missingFonts.length} font file(s) referenced by the CSS are not in public/.\n` +
    "Each is a 404, and the page falls back to a system face without saying so.\n" +
    "Hugo only publishes an asset something asks for -- see layouts/partials/fonts.html.\n\n" +
    missingFonts.map(o => `  ${o}`).join("\n") + "\n"
  );
  process.exit(1);
}

console.log(`check-build-output: no development URLs, no missing fonts`);
