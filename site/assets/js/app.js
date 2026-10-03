/**
 * Tetrak OCR — the small amount of behaviour the site actually needs.
 *
 * Everything here genuinely requires the browser: a search UI, a theme the
 * reader chooses, and a clipboard. Everything else — the search index, the
 * benchmark table, image resizing — is built. That split is the project's
 * architectural principle applied to its own site.
 */

// --- Theme -------------------------------------------------------------------
// The stored choice is applied before first paint by an inline script in
// baseof.html; this only handles the toggle.

const THEME_KEY = "theme";

function currentTheme() {
  const stamped = document.documentElement.getAttribute("data-theme");
  if (stamped) return stamped;
  // Nothing stamped means "follow the system", so report what the system says
  // rather than assuming light — otherwise the first click is a no-op for
  // anyone whose OS is already dark.
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function initTheme() {
  const button = document.querySelector("[data-theme-toggle]");
  if (!button) return;

  const paint = () => {
    button.textContent = currentTheme() === "dark" ? "◑" : "◐";
  };

  button.addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch {
      // Private mode. The choice still applies to this page view.
    }
    paint();
  });

  paint();
}

// --- Copy buttons ------------------------------------------------------------
// Added by script rather than baked into the markup: a reader without
// JavaScript should not be shown a button that cannot work.

function initCopyButtons() {
  document.querySelectorAll(".highlight").forEach(block => {
    const pre = block.querySelector("pre");
    if (!pre) return;

    const button = document.createElement("button");
    button.type = "button";
    button.className = "copy-btn";
    button.textContent = "Copy";

    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(pre.innerText);
        button.textContent = "Copied";
      } catch {
        button.textContent = "Press ⌘C";
      }
      setTimeout(() => {
        button.textContent = "Copy";
      }, 1300);
    });

    block.appendChild(button);
  });
}

// --- Search ------------------------------------------------------------------
// The index is a static JSON file built by Hugo. Fetched once on first open and
// filtered in memory: no search service, no index assembled in the browser,
// nothing fetched per keystroke.

const search = {
  index: null,
  loading: null
};

async function loadIndex(url) {
  if (search.index) return search.index;
  if (!search.loading) {
    search.loading = fetch(url)
      .then(r => (r.ok ? r.json() : []))
      .then(data => {
        search.index = data;
        return data;
      })
      .catch(() => {
        search.index = [];
        return search.index;
      });
  }
  return search.loading;
}

function scoreEntry(entry, terms) {
  // Title matches outrank body matches, and every term must appear somewhere —
  // an AND across terms, so a second word narrows rather than widens. Enough
  // for fourteen pages; a ranking library would be more machinery than this
  // corpus justifies.
  const title = entry.title.toLowerCase();
  const section = (entry.section || "").toLowerCase();
  const text = (entry.text || "").toLowerCase();

  let score = 0;
  for (const term of terms) {
    if (title.includes(term)) score += 10;
    else if (section.includes(term)) score += 4;
    else if (text.includes(term)) score += 1;
    else return 0;
  }
  return score;
}

function escapeHTML(value) {
  return String(value).replace(
    /[&<>"']/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#39;" })[c]
  );
}

function initSearch() {
  const openers = document.querySelectorAll("[data-search-open]");
  if (!openers.length) return;

  const indexURL = document.documentElement.dataset.searchIndex || "index.json";

  const overlay = document.createElement("div");
  overlay.className = "search";
  overlay.hidden = true;
  overlay.innerHTML = `
    <div class="search__panel" role="dialog" aria-modal="true" aria-label="Search">
      <input class="search__input" type="search" placeholder="Search the documentation…" autocomplete="off">
      <div class="search__results"></div>
      <div class="search__foot"><span data-count></span><span>Esc to close</span></div>
    </div>`;
  document.body.appendChild(overlay);

  const input = overlay.querySelector(".search__input");
  const results = overlay.querySelector(".search__results");
  const count = overlay.querySelector("[data-count]");
  let lastFocused = null;

  const render = (matches, query) => {
    if (!query) {
      results.innerHTML = "";
      count.textContent = "";
      return;
    }
    if (!matches.length) {
      results.innerHTML = `<p class="search__empty">No pages match “${escapeHTML(query)}”.</p>`;
      count.textContent = "0 pages";
      return;
    }
    results.innerHTML = matches
      .map(
        m => `
        <a class="search__hit" href="${escapeHTML(m.url)}">
          <span class="search__section">${escapeHTML(m.section)}</span>
          <span class="search__title">${escapeHTML(m.title)}</span>
        </a>`
      )
      .join("");
    count.textContent = `${matches.length} page${matches.length === 1 ? "" : "s"}`;
  };

  const runQuery = () => {
    const query = input.value.trim();
    const terms = query.toLowerCase().split(/\s+/).filter(Boolean);
    if (!terms.length) {
      render([], "");
      return;
    }

    const matches = (search.index || [])
      .map(entry => ({ entry, score: scoreEntry(entry, terms) }))
      .filter(m => m.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 8)
      .map(m => m.entry);

    render(matches, query);
  };

  const open = async () => {
    lastFocused = document.activeElement;
    overlay.hidden = false;
    input.value = "";
    render([], "");
    input.focus();
    await loadIndex(indexURL);
    // Re-run whatever was typed while the index was still in flight. Without
    // this, typing faster than the fetch leaves "No pages match" on screen
    // permanently, because nothing re-renders when the index finally lands --
    // the index is only consulted on an input event. On a fast connection the
    // race is invisible; CI is slow enough to lose it, which is how it showed.
    if (input.value) runQuery();
  };

  const close = () => {
    overlay.hidden = true;
    if (lastFocused) lastFocused.focus();
  };

  input.addEventListener("input", runQuery);

  openers.forEach(b => b.addEventListener("click", open));
  overlay.addEventListener("click", e => {
    if (e.target === overlay) close();
  });

  document.addEventListener("keydown", e => {
    // `/` opens, unless the reader is already typing into something.
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if (e.key === "/" && overlay.hidden && !typing) {
      e.preventDefault();
      open();
    }
    if (e.key === "Escape" && !overlay.hidden) close();
  });
}

// --- Lightbox ----------------------------------------------------------------
// The corpus pages tell the reader to click an item to see it full size, and
// judging these scans is the whole point of that page — a thumbnail cannot show
// why the 1930 newsprint is hard. Replaces the glightbox plugin mkdocs
// supplied. The anchor already points at the large rendition, so with no
// JavaScript the click still works; this only upgrades it to an overlay.

function initLightbox() {
  const links = document.querySelectorAll("[data-lightbox]");
  if (!links.length) return;

  const overlay = document.createElement("div");
  overlay.className = "lightbox-overlay";
  overlay.hidden = true;
  // tabindex="-1" on the dialog: a plain <div> cannot take focus, so calling
  // focus() on it silently does nothing and a keyboard or screen-reader user is
  // left on the thumbnail behind the overlay, reading the page underneath.
  overlay.innerHTML = `
    <div class="lightbox-overlay__inner" role="dialog" aria-modal="true" aria-label="Full-size scan" tabindex="-1">
      <img alt="">
      <p class="lightbox-overlay__caption"></p>
    </div>`;
  document.body.appendChild(overlay);

  const dialog = overlay.querySelector(".lightbox-overlay__inner");
  const img = overlay.querySelector("img");
  const caption = overlay.querySelector(".lightbox-overlay__caption");
  let lastFocused = null;

  const close = () => {
    overlay.hidden = true;
    img.removeAttribute("src");
    if (lastFocused) lastFocused.focus();
  };

  links.forEach(link => {
    link.addEventListener("click", e => {
      // Let a modified click do what the reader asked: new tab, download, save.
      if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
      e.preventDefault();
      lastFocused = link;
      img.src = link.href;
      img.alt = link.querySelector("img")?.alt || "";
      caption.textContent = link.dataset.title || "";
      overlay.hidden = false;
      dialog.focus();
    });
  });

  overlay.addEventListener("click", close);
  document.addEventListener("keydown", e => {
    if (e.key === "Escape" && !overlay.hidden) close();
  });
}

// --- Mobile nav --------------------------------------------------------------

function initMenu() {
  const button = document.querySelector("[data-menu-toggle]");
  const nav = document.querySelector(".masthead__nav");
  if (!button || !nav) return;

  button.setAttribute("aria-expanded", "false");
  button.addEventListener("click", () => {
    const open = nav.classList.toggle("is-open");
    button.setAttribute("aria-expanded", String(open));
  });
}

initTheme();
initCopyButtons();
initSearch();
initLightbox();
initMenu();
