import { expect, test, type APIRequestContext } from "@playwright/test";
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { join, relative } from "node:path";

/**
 * Smoke tests for the Tetrak OCR site.
 *
 * These check the things a passing Hugo build cannot: that the benchmark table
 * carries the real numbers, that the behaviour attached by script actually
 * attaches, and that the page does not scroll sideways. Every one of them
 * corresponds to something that broke during the migration while the build
 * stayed green.
 */

test("the landing page renders with its branding", async ({ page }) => {
  await page.goto("./");
  await expect(page).toHaveTitle("Tetrak OCR");
  await expect(page.locator(".masthead__name")).toHaveText("Tetrak OCR");
});

test("every real page has exactly one h1, including the home page", async ({ page, request, baseURL }) => {
  // The home page shipped with no h1 at all: layouts/index.html overrides the
  // `main` block and used to emit only .Content, so it never got the
  // `<h1>{{ .Title }}</h1>` that _default/single.html gives every other page.
  // Nothing hid it and nothing failed -- it was simply absent from the one page
  // most likely to be linked to and indexed.
  // allPages, not a hand-rolled sitemap parse: the sitemap carries production
  // URLs and the helper remaps them onto the local origin. Parsing it here
  // instead is how this suite once ended up reporting on the deployed site.
  const bad: string[] = [];
  for (const url of await allPages(request, baseURL!)) {
    await page.goto(url);
    // Alias stubs are meta-refresh redirects with no content of their own.
    if (await page.locator('meta[http-equiv="refresh"]').count()) continue;
    const n = await page.locator("main h1").count();
    if (n !== 1) bad.push(`${url} has ${n}`);
  }
  expect(bad, `pages without exactly one h1:\n${bad.join("\n")}`).toHaveLength(0);
});

test("the benchmark table is built from the CSV, not transcribed", async ({ page }) => {
  await page.goto("research/");

  const table = page.locator("table.benchmark").first();
  await expect(table).toBeVisible();

  // Every fixture plus the Average row, counted off the CSV itself: the page
  // must follow the data, and a hardcoded count broke when the corpus doubled.
  const csv = readFileSync(join(__dirname, "..", "..", "evaluation", "ocr", "benchmark.csv"), "utf8");
  const rows = csv.trim().split("\n").length - 1;
  await expect(table.locator("tbody tr")).toHaveCount(rows);

  // A value that only exists if the CSV was actually read.
  await expect(table).toContainText("kinema-theater-ad-1920.tif");

  // Claude is marked as a ceiling reference rather than a competitor.
  await expect(page.locator(".benchmark__ref").first()).toBeVisible();
});

test("the walkthrough renders its figures from the CSV, not from prose", async ({ page }) => {
  // The walkthrough carries the same argument as the slide deck, and both read
  // site/data/walkthrough.toml for the prose and evaluation/benchmark.csv for
  // every number. The deck's previous version had the figures typed into its
  // source and disagreed with the harness within a fortnight; this checks the
  // page cannot repeat that.
  await page.goto("research/");

  const csv = readFileSync(join(__dirname, "..", "..", "evaluation", "ocr", "benchmark.csv"), "utf8");
  const header = csv.split("\n")[0].split(",");
  // Five document plates, each with a full set of per-engine figures. The
  // count is derived from the CSV header, like every other count here — a
  // hardcoded 6 broke the day Vision became the eighth backend.
  await expect(page.locator(".wt-plate")).toHaveCount(5);
  const firstScores = page.locator(".wt-scores").first();
  await expect(firstScores.locator(".wt-scores__row")).toHaveCount(header.filter(c => c.endsWith("_chr")).length);

  // Best local is marked, and the ceiling is marked as a ceiling.
  await expect(firstScores.locator(".is-best").first()).toBeVisible();
  await expect(firstScores.locator(".is-ceiling")).toHaveCount(1);
});

test("the walkthrough shows the whole corpus and gives it the full column", async ({ page }) => {
  await page.goto("research/");

  // Nine items, each one a lightbox into its full-size rendition.
  await expect(page.locator(".wt-sheet__item")).toHaveCount(9);

  // `wide: true` collapses the rail track. Without the modifier .page reserves
  // 220px plus the gap for a rail it never renders, and the page sits off
  // centre — which is invisible until you put another page beside it.
  await expect(page.locator("main.page")).toHaveClass(/page--wide/);
  await expect(page.locator(".rail")).toHaveCount(0);
});

test("the seconds view labels its summary row as a total, not an average", async ({ page }) => {
  // The harness writes totals into the Average row's _sec columns. Labelling
  // that row "Average" would publish something false; it caught us once.
  await page.goto("research/in-depth/");
  const seconds = page.locator("table.benchmark").nth(1);
  await expect(seconds.locator(".benchmark__summary")).toContainText("Total seconds");
});

test("search finds pages by body text, not just titles", async ({ page }) => {
  await page.goto("research/");
  await page.locator("[data-search-open]").click();

  const input = page.locator(".search__input");
  await expect(input).toBeFocused();
  await input.fill("triage");

  // "triage" appears below the fold on most of these pages. A title-only or
  // truncated index finds one or two; the full index finds several.
  await expect(page.locator(".search__hit").first()).toBeVisible();
  const hits = await page.locator(".search__hit").count();
  expect(hits).toBeGreaterThan(3);

  await page.keyboard.press("Escape");
  await expect(page.locator(".search")).toBeHidden();
});

test("search still works when the index is slow to arrive", async ({ page }) => {
  // The index is fetched when the modal opens, and results only rendered on an
  // input event. Typing faster than the fetch therefore left "No pages match"
  // on screen for good, since nothing re-rendered once the index landed. It
  // passed locally on an instant fetch and failed in CI, which is the tell for
  // a race rather than a broken feature -- and a reader on a slow connection
  // would have hit it every time.
  await page.route("**/index.json", async route => {
    await new Promise(resolve => setTimeout(resolve, 1200));
    await route.continue();
  });

  await page.goto("research/");
  await page.locator("[data-search-open]").click();
  await page.locator(".search__input").fill("triage");

  await expect(page.locator(".search__hit").first()).toBeVisible({ timeout: 10_000 });
  await expect(page.locator(".search__empty")).toHaveCount(0);
});

test("the theme toggle flips and persists", async ({ page }) => {
  await page.goto("./");
  const html = page.locator("html");

  await page.locator("[data-theme-toggle]").click();
  const chosen = await html.getAttribute("data-theme");
  expect(chosen).toBeTruthy();

  const stored = await page.evaluate(() => localStorage.getItem("theme"));
  expect(stored).toBe(chosen);

  // And it survives a reload, applied before paint.
  await page.reload();
  await expect(html).toHaveAttribute("data-theme", chosen!);
});

test("copy buttons attach to code blocks", async ({ page }) => {
  await page.goto("install/");
  await expect(page.locator(".copy-btn").first()).toBeVisible();
});

test("the API reference is generated from docstrings", async ({ page }) => {
  await page.goto("reference/api/");
  await expect(page.locator(".generated-note")).toBeVisible();
  // A signature can only be here if the generator introspected the package.
  await expect(page.locator("h3").first()).toContainText("get_backend");
});

/**
 * Every page on the site, read from the sitemap Hugo generates, so a page added
 * later is covered without anyone remembering to list it here.
 */
async function allPages(request: APIRequestContext, baseURL: string): Promise<string[]> {
  const xml = await (await request.get(new URL("sitemap.xml", baseURL).href)).text();
  const locs = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
  expect(locs.length, "sitemap is empty").toBeGreaterThan(10);

  // The sitemap carries production URLs, because that is what a sitemap is for.
  // Visiting them directly would crawl the deployed site over the network and
  // report on that instead of the working tree -- which is exactly what these
  // tests did until a deliberately broken page kept passing. Keep the path,
  // drop the origin.
  const base = new URL(baseURL);
  return locs.map((loc) => {
    const path = new URL(loc).pathname.replace(/^\/+/, "");
    const prefix = base.pathname.replace(/^\/+/, "");
    return new URL(path.startsWith(prefix) ? `/${path}` : `${prefix}${path}`, base.origin).href;
  });
}

test("every image on every page actually loads", async ({ page, request, baseURL }) => {
  // The migration published a site on which all 19 corpus images were dead
  // links, behind a green build and a green test suite: the markdown still
  // carried mkdocs-relative paths. Parsing the HTML for src attributes is what
  // missed it the first time -- Hugo's minifier strips the quotes, so the
  // pattern found nothing and reported success. Asking the browser whether the
  // bytes arrived cannot be fooled that way.
  const broken: string[] = [];

  for (const url of await allPages(request, baseURL!)) {
    await page.goto(url);
    // Lazy images below the fold never load in a short viewport, so force them.
    await page.evaluate(() =>
      document.querySelectorAll("img[loading=lazy]").forEach((i) => i.setAttribute("loading", "eager"))
    );
    await page.waitForLoadState("networkidle");

    const bad = await page.evaluate(() =>
      [...document.querySelectorAll("img")]
        // The lightbox overlay holds an empty <img> until something is opened
        // into it. No src is a placeholder, not a broken image.
        .filter((i) => i.getAttribute("src"))
        .filter((i) => !i.complete || i.naturalWidth === 0)
        .map((i) => i.getAttribute("src")!)
    );
    broken.push(...bad.map((src) => `${new URL(url).pathname} -> ${src}`));
  }

  expect(broken, `broken images:\n${broken.join("\n")}`).toHaveLength(0);
});

test("every internal link resolves", async ({ page, request, baseURL }) => {
  // The masthead and footer built their links with `"/path" | relURL`. A
  // leading slash makes Hugo treat the path as already rooted, so it drops the
  // baseURL's /ocr-pipeline/ segment -- every nav link pointed at the domain
  // root and the whole navigation was dead. Nothing failed: the links were
  // well-formed, just aimed at the wrong place. Only following them finds that.
  const seen = new Map<string, number>();
  const bad: string[] = [];

  for (const url of await allPages(request, baseURL!)) {
    await page.goto(url);
    const hrefs = await page.evaluate(() =>
      [...document.querySelectorAll("a[href]")]
        .map(a => (a as HTMLAnchorElement).href)
        .filter(h => h.startsWith(location.origin))
    );

    for (const href of new Set(hrefs)) {
      const target = href.split("#")[0];
      if (!seen.has(target)) {
        seen.set(target, (await request.get(target)).status());
      }
      const status = seen.get(target)!;
      if (status >= 400) bad.push(`${new URL(url).pathname} -> ${new URL(target).pathname} (${status})`);
    }
  }

  expect(seen.size, "no internal links found at all").toBeGreaterThan(5);
  expect(bad, `dead links:\n${[...new Set(bad)].join("\n")}`).toHaveLength(0);
});

test("the masthead links into the site, not to the domain root", async ({ page, baseURL }) => {
  // Distinct from the check above because a link to "/" is not dead -- it is a
  // real page, just the wrong one, and served locally it silently resolves.
  // Every masthead link must sit under the baseURL's path.
  //
  // Honest caveat since the move to tetrak.dev: the site now publishes at a
  // root baseURL, so `prefix` is "/" and every absolute link passes. This
  // assertion currently proves only that the masthead has links at all. It is
  // kept rather than deleted because it costs nothing and becomes load-bearing
  // again the moment anything is served from a subdirectory -- but do not read
  // it as live cover for the bug in its name.
  await page.goto("research/");
  const prefix = new URL(baseURL!).pathname;

  const hrefs = await page.evaluate(() =>
    [...document.querySelectorAll(".masthead__nav a, .masthead__brand")]
      .map(a => new URL((a as HTMLAnchorElement).href).pathname)
  );

  expect(hrefs.length, "masthead has no links").toBeGreaterThan(5);
  for (const href of hrefs) {
    expect(href.startsWith(prefix), `${href} is outside ${prefix}`).toBe(true);
  }
});

test("links into the repository point at files that exist", async () => {
  // The internal-link check only follows same-origin URLs, so links out to
  // GitHub go unverified. The content port rewrote `.md` links into Hugo's
  // directory-style form and applied that to absolute github.com URLs too,
  // turning four of them into 404s -- SOURCES.md became SOURCES/.
  //
  // Checked against the filesystem rather than by fetching: it needs no
  // network, cannot flake, and the repository is right here.
  // Two roots now: the site owns content/, but the links point into the
  // repository, which is a level above it since the site moved into site/.
  const siteRoot = join(__dirname, "..");
  const repoRoot = join(siteRoot, "..");
  // The repository IS now scattercode/tetrak. It was held back at
  // ocr-pipeline while the site published under /ocr-pipeline/ on GitHub
  // Pages; moving to tetrak.dev removed that constraint, and the rename
  // followed. GitHub redirects the old URL, which is exactly why this pattern
  // has to track the new name: a stale link would keep working in a browser
  // and quietly stop being checked here.
  const pattern = /https:\/\/github\.com\/scattercode\/tetrak\/blob\/main\/([^)"'|\s]+)/g;
  const bad: string[] = [];

  const walk = (dir: string): string[] =>
    readdirSync(dir, { withFileTypes: true }).flatMap(e =>
      e.isDirectory() ? walk(join(dir, e.name)) : e.name.endsWith(".md") ? [join(dir, e.name)] : []
    );

  // The repository's own top-level markdown carries these links too --
  // LICENSING.md alone has four, and they are the ones a licence reader
  // follows. Scanning only site/content/ left them unguarded, which the
  // rename to scattercode/tetrak made concrete: every one of them was
  // rewritten and nothing here would have noticed if a path went with it.
  // Top level only, not a recursive walk: the repository root holds
  // node_modules/, public/ and product/, and none of them are ours to check.
  const topLevelDocs = readdirSync(repoRoot, { withFileTypes: true })
    .filter(e => e.isFile() && e.name.endsWith(".md"))
    .map(e => join(repoRoot, e.name));

  for (const file of [...walk(join(siteRoot, "content")), ...topLevelDocs]) {
    const body = readFileSync(file, "utf8");
    for (const m of body.matchAll(pattern)) {
      const target = m[1].replace(/[.,)]+$/, "");
      if (!existsSync(join(repoRoot, target))) {
        bad.push(`${relative(repoRoot, file)} -> ${target}`);
      }
    }
  }

  // The pattern above only matches absolute github.com/.../blob/main URLs, so
  // the repo-relative links in the top-level docs went unchecked -- CLAUDE.md
  // pointed at site/content/research/method.md and results.md for two days
  // after those pages were consolidated into one narrative.
  //
  // Top-level docs only. The same syntax inside site/content/ is a *site* link
  // resolved by Hugo against the page's URL, not a path into the repository,
  // and "every internal link resolves" already covers those.
  const relPattern = /\]\((?!https?:|#|mailto:)([^)\s]+\.(?:md|py|ya?ml|toml|txt|json|sh))\)/g;
  for (const file of topLevelDocs) {
    for (const m of readFileSync(file, "utf8").matchAll(relPattern)) {
      const target = m[1];
      const resolved = join(repoRoot, target);

      // A link carrying `..` resolves outside the repository, where something
      // may well exist -- the sibling checkouts share a parent directory. That
      // would pass the existence check while pointing at a file no clone of
      // this repository contains. Escaping the root is itself the defect, so
      // it is reported rather than followed.
      const inside = relative(repoRoot, resolved);
      if (inside.startsWith("..")) {
        bad.push(`${relative(repoRoot, file)} -> ${target} (escapes the repository)`);
        continue;
      }
      if (!existsSync(resolved)) {
        bad.push(`${relative(repoRoot, file)} -> ${target}`);
      }
    }
  }

  expect(bad, `repo links with no file behind them:\n${[...new Set(bad)].join("\n")}`).toHaveLength(0);
});

test("the site does not link into internal product material", async () => {
  // product/ is the internal product-management zone: briefs, research notes,
  // the roadmap, licence audits. The site is public-facing, and a results page
  // linking out to an internal roadmap couples the two -- it also broke the
  // moment product-management/ was renamed to product/.
  //
  // The site may of course be *informed* by that material. It must not cite it.
  const siteRoot = join(__dirname, "..");
  const offenders: string[] = [];

  const walk = (dir: string): string[] =>
    readdirSync(dir, { withFileTypes: true }).flatMap(e =>
      e.isDirectory() ? walk(join(dir, e.name)) : e.name.endsWith(".md") ? [join(dir, e.name)] : []
    );

  for (const file of walk(join(siteRoot, "content"))) {
    const body = readFileSync(file, "utf8");
    for (const m of body.matchAll(/(?:blob\/main\/|\]\(\s*\.{0,2}\/?)(product(?:-management)?)\//g)) {
      offenders.push(`${relative(siteRoot, file)} -> ${m[1]}/`);
    }
  }

  expect(offenders, `site content citing internal product material:\n${[...new Set(offenders)].join("\n")}`)
    .toHaveLength(0);
});

test("an included file does not put its own title on the page as well", async ({ page }) => {
  // LICENSING.md is a standalone document at the repository root and carries its
  // own "# Licensing" for the benefit of anyone reading it on GitHub. The page
  // template already renders a title from front matter, so including the file
  // whole produced two h1s saying the same thing. The build stayed green
  // throughout, which is why this is a test rather than a code comment.
  await page.goto("reference/licensing/");
  await expect(page.locator("main h1")).toHaveCount(1);

  // The rest of the file still has to arrive: stripping too much would leave a
  // page that passes the count above and says nothing.
  //
  // A floor rather than an exact count. LICENSING.md gains a section whenever
  // the project takes on material with its own terms -- the Armenian model
  // added one -- and pinning the exact number turned each of those into a
  // failing build on main that had nothing to do with the change. Duplication,
  // which is what this test exists to catch, is already covered by the h1
  // count above.
  expect(await page.locator("main h2").count()).toBeGreaterThanOrEqual(4);
  await expect(page.locator("main")).toContainText("three kinds of material");
});

test("deep links land on a heading that exists, not just a page that does", async ({ page, request, baseURL }) => {
  // "every internal link resolves" strips the fragment -- `href.split("#")[0]`
  // -- so it proves the page exists and says nothing about the heading. When
  // the research narrative moved to /research/in-depth/ that left twelve links
  // pointing at anchors on a page that no longer had them, with a green build
  // and a green suite. This checks the other half.
  const pages = await allPages(request, baseURL!);
  const idsFor = new Map<string, Set<string>>();
  const bad: string[] = [];

  for (const url of pages) {
    await page.goto(url);
    if (await page.locator('meta[http-equiv="refresh"]').count()) continue;

    const links = await page.locator('main a[href*="#"]').evaluateAll(as =>
      as.map(a => (a as HTMLAnchorElement).href).filter(h => h.includes("#")));

    for (const href of links) {
      const u = new URL(href);
      if (u.origin !== new URL(baseURL!).origin || !u.hash || u.hash === "#") continue;
      const key = u.origin + u.pathname;
      if (!idsFor.has(key)) {
        const p2 = await request.get(key);
        const html = await p2.text();
        idsFor.set(key, new Set([...html.matchAll(/\bid=(?:"([^"]+)"|([^\s>]+))/g)].map(m => m[1] ?? m[2])));
      }
      const id = decodeURIComponent(u.hash.slice(1));
      if (!idsFor.get(key)!.has(id)) bad.push(`${new URL(url).pathname} -> ${u.pathname}#${id}`);
    }
  }
  expect([...new Set(bad)], `links to headings that do not exist:\n${[...new Set(bad)].join("\n")}`).toHaveLength(0);
});

test("no mkdocs markup leaks into the rendered text", async ({ page, request, baseURL }) => {
  // attr_list and md_in_html are mkdocs-material extensions. Hugo renders the
  // markdown and then prints the attribute list as visible text, so `{
  // loading=lazy }` and `{ .glightbox ... }` appeared in the prose on two
  // pages. Nothing about that fails a build -- it is valid markdown producing
  // wrong output -- so it needs checking against what a reader sees.
  const offenders: string[] = [];

  for (const url of await allPages(request, baseURL!)) {
    await page.goto(url);
    const text = await page.locator("body").innerText();
    for (const pattern of ["{ loading=", "{ .glightbox", "glightbox", "data-type=\"image\"", " markdown>"]) {
      if (text.includes(pattern)) offenders.push(`${new URL(url).pathname}: ${pattern}`);
    }
  }

  expect(offenders, `leaked markup:\n${offenders.join("\n")}`).toHaveLength(0);
});

test("the lightbox opens a corpus scan, takes focus, and closes again", async ({ page }) => {
  await page.goto("reference/corpus/");

  await page.locator("[data-lightbox]").first().click();
  const overlay = page.locator(".lightbox-overlay");
  await expect(overlay).toBeVisible();
  await expect(overlay.locator("img")).toBeVisible();
  // The caption carries the provenance, which is the reason for enlarging it.
  await expect(overlay.locator(".lightbox-overlay__caption")).not.toBeEmpty();

  // Focus must move into the dialog. A plain <div> is not focusable, so calling
  // focus() on it does nothing at all and a keyboard user stays on the page
  // behind the overlay -- silently, since the overlay still looks correct.
  await expect(overlay.locator(".lightbox-overlay__inner")).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(overlay).toBeHidden();
});

test("themed figures show exactly one rendition", async ({ page }) => {
  // Both renditions ship and CSS picks one. A shortcode bug put the resource's
  // path into the class attribute instead of "light"/"dark", so
  // .figure__light / .figure__dark matched nothing and the page displayed the
  // chart twice, stacked. Both images loaded, so the image test passed.
  await page.goto("research/");

  const figure = page.locator(".figure--themed").first();
  await expect(figure).toBeVisible();
  await expect(figure.locator(".figure__light, .figure__dark")).toHaveCount(2);

  const visible = await figure.evaluate(f =>
    [...f.querySelectorAll("img")].filter(i => getComputedStyle(i).display !== "none").length
  );
  expect(visible, "exactly one rendition should be displayed").toBe(1);
});

test("the seconds view never marks a best value", async ({ page }) => {
  // "Best" is computed from the accuracy columns. Bolding it over a duration
  // would read as "fastest" and state something the data does not.
  await page.goto("research/in-depth/");
  const seconds = page.locator("table.benchmark").nth(1);
  await expect(seconds.locator(".is-best")).toHaveCount(0);
});

test("no page scrolls sideways", async ({ page }) => {
  // Wide content -- the nine-column benchmark table -- must scroll inside its
  // own container, never the body.
  //
  // Real pages only. research/walkthrough/ was in this list until the
  // walkthrough became the section index and that path turned into an alias:
  // the meta-refresh then navigated away underneath page.evaluate, which fails
  // with "Execution context was destroyed" -- and does so on timing, so it
  // passed locally and failed in CI.
  for (const path of ["./", "research/", "research/in-depth/", "reference/engines/", "articles/", "tags/"]) {
    await page.goto(path);
    const overflows = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth
    );
    expect(overflows, `${path} scrolls sideways`).toBe(false);
  }
});

test("the masthead fits a phone, burger included", async ({ page }) => {
  // The check above runs at the default 1280px viewport, where the masthead has
  // room to spare. It had none on a phone: below the 1000px breakpoint the nav
  // is hidden but the whole tools row remains, and at 390px the row overran the
  // viewport -- putting the burger, the only way to reach the nav at that
  // width, off the right-hand edge.
  //
  // 320px is the narrowest screen worth supporting; 390px is a current iPhone.
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 800 });
    await page.goto("articles/");

    const burger = page.locator("[data-menu-toggle]");
    await expect(burger).toBeVisible();
    const box = await burger.boundingBox();
    expect(box, `no burger at ${width}px`).not.toBeNull();
    expect(box!.x, `burger starts off-screen at ${width}px`).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width, `burger runs off-screen at ${width}px`).toBeLessThanOrEqual(width);

    const overflows = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth
    );
    expect(overflows, `the page scrolls sideways at ${width}px`).toBe(false);
  }
});

// --- Articles ----------------------------------------------------------------

test("the articles section is in the nav and lists what is in it", async ({ page }) => {
  await page.goto("articles/");

  await expect(page.locator('.masthead__nav a[aria-current="page"]')).toHaveText("Articles");

  // At least one row, and every row carries the three things a listing has to
  // give a reader before they click: a date, a linked title and a lead.
  const rows = page.locator(".article-row");
  expect(await rows.count()).toBeGreaterThan(0);

  const first = rows.first();
  await expect(first.locator("time")).not.toBeEmpty();
  await expect(first.locator(".article-row__title a")).not.toBeEmpty();
  await expect(first.locator(".article-row__lead")).not.toBeEmpty();
});

test("articles are listed newest first, under the year they were published", async ({ page }) => {
  await page.goto("articles/");

  // Years descend, and the rows inside each year descend too. Hugo's default
  // page order is by weight then date, which is *not* date-descending, so this
  // is the ordering the layout asks for rather than one it inherits.
  const years = await page.locator(".articles__year-label").evaluateAll(
    hs => hs.map(h => h.textContent!.trim())
  );
  expect(years).toEqual([...years].sort().reverse());

  const dates = await page.locator(".article-row time").evaluateAll(
    ts => ts.map(t => t.getAttribute("datetime")!)
  );
  expect(dates).toEqual([...dates].sort().reverse());

  // Every year heading must actually head the rows filed under it, or the
  // grouping is decoration.
  for (const group of await page.locator(".articles__year").all()) {
    const year = (await group.locator(".articles__year-label").textContent())!.trim();
    const inGroup = await group.locator(".article-row time").evaluateAll(
      ts => ts.map(t => t.getAttribute("datetime")!.slice(0, 4))
    );
    expect(new Set(inGroup)).toEqual(new Set([year]));
  }
});

test("an article carries its date, reading time and a byline from the author register", async ({ page }) => {
  await page.goto("articles/");
  await page.locator(".article-row__title a").first().click();

  const meta = page.locator(".article-meta");
  await expect(meta.locator("time")).toHaveAttribute("datetime", /^\d{4}-\d{2}-\d{2}$/);
  await expect(meta).toContainText(/\d+ min read/);

  // The byline is a key resolved against data/authors.toml, not a name typed
  // into front matter -- an unknown key fails the build in partials/author.html.
  // Checking the rendered name against the file is the only half of that
  // bargain a browser test can see, and it is the half that would go wrong
  // silently if the partial ever stopped resolving and started printing the key.
  const register = readFileSync(join(__dirname, "..", "data", "authors.toml"), "utf8");
  const names = [...register.matchAll(/^\s*name\s*=\s*"([^"]+)"/gm)].map(m => m[1]);
  expect(names.length, "data/authors.toml lists no authors").toBeGreaterThan(0);

  // textContent, not innerText: the meta line is rendered uppercase by CSS, and
  // innerText returns what is painted rather than what the template wrote.
  const byline = (await page.locator(".article-meta span").last().textContent())!;
  expect(names).toContain(byline.trim());

  // And the same person again at the foot, with a way to read more about them.
  await expect(page.locator(".article-author__name")).toHaveText(byline.trim());
  await expect(page.locator('.article-author__links a[href$="/about/"]')).toBeVisible();
});

test("articles publish at a flat URL, and the date directories are not pages", async ({ page, request, baseURL }) => {
  // Articles are filed under content/articles/<year>/<month>/ so the section
  // stays navigable on disk. Those directories hold no _index.md, so Hugo does
  // not make sections of them -- if one ever acquired one, /articles/2026/
  // would start publishing a second, unstyled index of the same articles.
  await page.goto("articles/");
  const href = await page.locator(".article-row__title a").first().getAttribute("href");

  // Compared as a path *below* the baseURL rather than matched against a
  // literal "/articles/...". Served from a subdirectory the href carries that
  // prefix, and a pattern anchored at the domain root quietly stops describing
  // anything -- it would still match nothing and fail, but for the wrong
  // reason. Same correction "the masthead links into the site" already makes:
  // strip the prefix, do not assume it is empty.
  const base = new URL(baseURL!);
  const prefix = base.pathname.replace(/\/$/, "");
  const path = new URL(href!, base).pathname;
  expect(path.startsWith(prefix), `${path} is outside ${base.pathname}`).toBe(true);
  expect(path.slice(prefix.length)).toMatch(/^\/articles\/\d{4}\/\d{2}\/[^/]+\/$/);

  // Absolute, so the request keeps the baseURL's path: a leading-slash path
  // handed to request.get is treated as already rooted and drops it, which is
  // the same trap the masthead links fell into.
  const yearIndex = new URL(path.replace(/^(.*\/articles\/\d{4}\/).*$/, "$1"), base.origin);
  expect((await request.get(yearIndex.href)).status()).toBe(404);
});

test("tags reach their articles, and are not title-cased on the way", async ({ page }) => {
  await page.goto("articles/");

  const tag = page.locator(".article-row .tag").first();
  const label = (await tag.textContent())!.trim();
  // Rendered uppercase by CSS; the text itself must stay as written, because
  // Hugo title-cases derived list titles and turned the tag `ocr` into "Ocr".
  expect(label).toBe(label.toLowerCase());

  await tag.click();
  await expect(page.locator("h1")).toContainText(`Tagged ${label}`);
  await expect(page.locator(".article-row")).not.toHaveCount(0);

  // And on to the index of every tag, with a count beside each.
  await page.locator('.articles__foot a[href$="/tags/"]').click();
  await expect(page.locator(".tag-list--index .tag").first()).toBeVisible();
  await expect(page.locator(".tag-list--index .tag__count").first()).toContainText(/^\d+$/);
});

test("the articles feed is generated and advertised on every page", async ({ page, request, baseURL }) => {
  // A blog with no feed is a blog nobody can follow, and a <link rel=alternate>
  // pointing at a file the build did not emit is worse than none: a feed reader
  // reports the site as broken rather than as having no feed.
  await page.goto("./");
  const feed = await page.locator('link[rel="alternate"][type*="rss"]').getAttribute("href");
  expect(feed, "no feed advertised in <head>").toBeTruthy();

  const response = await request.get(new URL(feed!, baseURL!).href);
  expect(response.status()).toBe(200);

  const xml = await response.text();
  const titles = [...xml.matchAll(/<title>([^<]*)<\/title>/g)].map(m => m[1]);
  // The channel title plus one per article.
  expect(titles.length).toBeGreaterThan(1);

  await page.goto("articles/");
  const listed = await page.locator(".article-row__title a").evaluateAll(
    as => as.map(a => a.textContent!.trim())
  );
  for (const title of listed) {
    expect(titles, `"${title}" is listed but not in the feed`).toContain(title);
  }
});

test("the register tables agree with the CSV they are generated from", async ({ page }) => {
  // These tables replaced two hand-typed copies that both went stale in the
  // same cell. Generating them only removes that failure if the rendered
  // numbers are actually the CSV's, so this reads the source of truth and
  // compares -- a wrong table would otherwise pass every other test here.
  const csv = readFileSync(join("..", "evaluation", "ocr", "registers.csv"), "utf8")
    .trim()
    .split(/\r?\n/)
    .map((line) => line.match(/("[^"]*"|[^,]+)/g)!.map((cell) => cell.replace(/^"|"$/g, "")));
  const header = csv[0];
  const mean = csv.find((row) => row[0] === "mean")!;
  const engines = header.filter((h) => h.endsWith("_chr")).map((h) => h.slice(0, -4));
  const registers = csv.slice(1).filter((row) => row[0] !== "mean");

  await page.goto("articles/2026/09/the-engine-we-had-left-out/");

  // Two tables: word recall by default, then character similarity.
  const tables = page.locator("table.benchmark");
  await expect(tables).toHaveCount(2);

  // Dynamic columns: one per engine in the CSV, plus the register name.
  await expect(tables.first().locator("thead th")).toHaveCount(engines.length + 1);

  // A row per register plus the mean.
  await expect(tables.first().locator("tbody tr")).toHaveCount(registers.length + 1);

  const cellFor = (row: string[], engine: string, metric: string) =>
    Number(row[header.indexOf(`${engine}_${metric}`)]).toFixed(3);

  for (const [index, metric] of ["wrd", "chr"].entries()) {
    const summary = tables.nth(index).locator("tr.benchmark__summary td");
    for (const [column, engine] of engines.entries()) {
      await expect(summary.nth(column)).toHaveText(cellFor(mean, engine, metric));
    }
    // Exactly one engine is marked best in the mean row, and it is the
    // highest in the CSV -- the cell the published claim turns on.
    const best = engines.reduce((a, b) =>
      Number(cellFor(mean, a, metric)) >= Number(cellFor(mean, b, metric)) ? a : b,
    );
    await expect(tables.nth(index).locator("tr.benchmark__summary .is-best")).toHaveCount(1);
    await expect(tables.nth(index).locator("tr.benchmark__summary .is-best")).toHaveText(
      cellFor(mean, best, metric),
    );
  }
});

test("the summary view carries both metrics and derives its register count", async ({ page }) => {
  // The engines page renders the same CSV through the other branch. Its
  // caption used to assert "eight registers" in prose; it now counts them,
  // so adding a register cannot leave the page describing the old scope.
  const csv = readFileSync(join("..", "evaluation", "ocr", "registers.csv"), "utf8")
    .trim()
    .split(/\r?\n/);
  const registerCount = csv.length - 2; // minus the header and the mean row

  await page.goto("reference/engines/");
  const table = page.locator("table.benchmark").filter({ hasText: "Char similarity" });
  await expect(table).toHaveCount(1);
  await expect(table.locator("thead th")).toHaveCount(3);
  await expect(table.locator("tbody tr")).toHaveCount(csv[0].split(",").filter((h) => h.endsWith("_chr")).length);
  await expect(page.locator("p.benchmark__caption")).toContainText(
    `${registerCount} evaluation registers`,
  );
});
