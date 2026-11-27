/**
 * Render the site's share card: the image a link to tetrak.dev shows when it
 * is pasted into Mastodon, Bluesky, LinkedIn, Slack or a chat window.
 *
 * Until November 2026 the site declared no Open Graph image at all, so a
 * shared link arrived as a bare URL. The two illustrations already in
 * assets/images/design/ are both about the OCR tool, and since brief 017 the
 * site is the home of every Tetrak tool and of the services, so neither can
 * stand for the whole site. This draws a card from the design system itself:
 * the paper ground, a clay rule, the name in Playfair Display and the home
 * page's standfirst in Source Serif 4.
 *
 * The standfirst is read from content/_index.md rather than typed in here, so
 * the card says what the home page says. It does not follow an edit on its
 * own, though: the output is a committed PNG, so re-run this after changing
 * the home page's standfirst.
 *
 * Rendered in the Chromium that Playwright already installs, with the fonts
 * vendored in assets/fonts/, the same way scripts/render-mermaid.mjs draws the
 * diagrams. It is not part of `prebuild`: the build host has no browser, and
 * the card changes about as often as the site's name does.
 *
 * PNG, not WebP, because several link-preview scrapers still do not read
 * WebP. 1200 by 630 is the size Open Graph consumers crop least.
 * layouts/partials/social.html publishes the file and reads its dimensions.
 *
 * Prerequisites: `npm install` and `npx playwright install chromium`.
 *
 * Run, from site/:
 *   node scripts/render-share-card.mjs
 */

import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { chromium } from "@playwright/test";

const SITE = join(import.meta.dirname, "..");
const FONTS = join(SITE, "assets", "fonts");
const HOME = join(SITE, "content", "_index.md");
const OUT = join(SITE, "assets", "images", "design", "share-card.png");

const WIDTH = 1200;
const HEIGHT = 630;

// The light-theme tokens from assets/scss/_tokens.scss. A share card has no
// dark rendition: the page it is pasted into chooses the surround, not us.
const TOKENS = {
  paper: "#f7f3ec",
  ink: "#1e1c19",
  inkSoft: "#6d675e",
  clay: "#b08d4f",
  clayDeep: "#8a6a33"
};

/** One front-matter string from the home page, or a failure that says which. */
function frontMatter(key) {
  const source = readFileSync(HOME, "utf8");
  const match = source.match(new RegExp(`^${key}:\\s*"(.*)"\\s*$`, "m"));
  if (!match) {
    throw new Error(`render-share-card: no quoted \`${key}\` in content/_index.md`);
  }
  return match[1];
}

/** A vendored font as a data URI, so the page needs no server to load it. */
function fontFace(family, file, weight) {
  const data = readFileSync(join(FONTS, file)).toString("base64");
  return `@font-face {
    font-family: "${family}";
    font-weight: ${weight};
    src: url("data:font/woff2;base64,${data}") format("woff2");
  }`;
}

const escapeHtml = text =>
  text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");

const title = frontMatter("title");
const standfirst = frontMatter("standfirst");

const html = `<!doctype html>
<html lang="en-gb">
<head>
<meta charset="utf-8">
<style>
  ${fontFace("Playfair Display", "playfair-display-700.woff2", 700)}
  ${fontFace("Source Serif 4", "source-serif-4-400.woff2", 400)}
  ${fontFace("IBM Plex Mono", "ibm-plex-mono-400.woff2", 400)}

  html, body { margin: 0; }

  /* Left-aligned with the air on the right, like every page on the site. */
  body {
    width: ${WIDTH}px;
    height: ${HEIGHT}px;
    box-sizing: border-box;
    padding: 84px 96px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    background: ${TOKENS.paper};
    color: ${TOKENS.ink};
  }

  /* The same 2px clay rule that sits above a person on the about page. */
  .rule {
    width: 96px;
    height: 2px;
    background: ${TOKENS.clay};
    margin-bottom: 40px;
  }

  .kicker {
    font-family: "IBM Plex Mono", monospace;
    font-size: 22px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: ${TOKENS.clayDeep};
    margin-bottom: 20px;
  }

  h1 {
    font-family: "Playfair Display", serif;
    font-weight: 700;
    font-size: 148px;
    line-height: 1.02;
    letter-spacing: -0.028em;
    text-transform: uppercase;
    margin: 0 0 36px;
  }

  .standfirst {
    font-family: "Source Serif 4", serif;
    font-size: 38px;
    line-height: 1.4;
    color: ${TOKENS.inkSoft};
    max-width: 880px;
    text-wrap: pretty;
    margin: 0;
  }
</style>
</head>
<body>
  <div class="rule"></div>
  <div class="kicker">tetrak.dev</div>
  <h1>${escapeHtml(title)}</h1>
  <p class="standfirst">${escapeHtml(standfirst)}</p>
</body>
</html>`;

const browser = await chromium.launch();
try {
  const page = await browser.newPage({
    viewport: { width: WIDTH, height: HEIGHT },
    deviceScaleFactor: 1
  });
  await page.setContent(html);
  // A screenshot taken before the faces have loaded is a card in Times.
  // Passed as a string because it runs in the page, not in Node, where this
  // file is linted and `document` does not exist.
  await page.evaluate("document.fonts.ready.then(() => true)");
  writeFileSync(OUT, await page.screenshot({ type: "png" }));
} finally {
  await browser.close();
}

console.log(`render-share-card: wrote ${OUT.slice(SITE.length + 1)} (${WIDTH}×${HEIGHT})`);
