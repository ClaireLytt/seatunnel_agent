"""CSS for the SeaTunnel Agent Gradio UI (Claude-style clean design)."""

from __future__ import annotations

# ------------------------------------------------------------------
# CSS — Claude-style clean design
# ------------------------------------------------------------------

_CUSTOM_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@1,700;1,800&display=swap');
/* ══════════════════════════════════════════
   Global — full viewport, no scroll on body
   ══════════════════════════════════════════ */
.gradio-container {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif !important;
    font-size: 11px !important;
    max-width: 100% !important;
    background: #fff !important;
    padding: 0 !important;
    height: 100vh !important;
    overflow: hidden !important;
}
.gradio-container > .main,
.gradio-container > .main > .wrap {
    height: 100vh !important;
    overflow: hidden !important;
    padding: 0 !important;
    gap: 0 !important;
    display: flex !important;
    flex-direction: column !important;
}
footer { display: none !important; }
/* Hide the multipage navbar entirely: navigation is hub cards + the 🏠
   button each page keeps in its top-right corner. The .nav-holder wrapper
   must go too — with only the inner nav hidden it still eats ~17px and
   clips the bottom strip of every 100vh page. */
.gradio-container nav,
.gradio-container .nav-holder { display: none !important; }
/* Suppress Gradio default block borders globally */
.gradio-container .block {
    border: none !important;
    box-shadow: none !important;
}

/* Standalone pages (history, favorites, schema, sql review, and any page
   carrying the generic .st-scroll-page marker — e.g. data skew) need
   scrolling. Only the outermost .gradio-container scrolls; everything
   inside is visible. */
body:has(.st-history-page),
body:has(.st-uitest-page),
body:has(.st-scroll-page) {
    overflow: hidden !important;
}
body:has(.st-history-page) .gradio-container,
body:has(.st-uitest-page) .gradio-container,
body:has(.st-scroll-page) .gradio-container {
    overflow-y: auto !important;
    overflow-x: hidden !important;
    height: 100vh !important;
}
body:has(.st-history-page) .gradio-container > .main,
body:has(.st-history-page) .gradio-container > .main > .wrap,
body:has(.st-uitest-page) .gradio-container > .main,
body:has(.st-uitest-page) .gradio-container > .main > .wrap,
body:has(.st-scroll-page) .gradio-container > .main,
body:has(.st-scroll-page) .gradio-container > .main > .wrap {
    overflow: visible !important;
    height: auto !important;
    min-height: auto !important;
}
body:has(.st-uitest-page) .gradio-container > .main > .wrap {
    max-width: 1500px !important;
    width: 100% !important;
    margin: 0 auto !important;
    padding: 14px 28px 48px !important;
}

/* Hub landing page: ten cards now exceed one viewport on short windows —
   unlock the outer container so the grid can scroll (same marker trick). */
body:has(.st-hub) {
    overflow: hidden !important;
}
body:has(.st-hub) .gradio-container {
    overflow-y: auto !important;
    overflow-x: hidden !important;
    height: 100vh !important;
}
body:has(.st-hub) .gradio-container > .main,
body:has(.st-hub) .gradio-container > .main > .wrap {
    overflow: visible !important;
    height: auto !important;
    min-height: auto !important;
}

/* ══════════════════════════════════════════
   Data Skew page polish (same scroll ergonomics as SQL Review)
   ══════════════════════════════════════════ */
body:has(.st-scroll-page) .gradio-container > .main > .wrap {
    max-width: 1500px !important;
    width: 100% !important;
    margin: 0 auto !important;
    padding: 14px 28px 48px !important;
}
/* SQL input box: fixed height with a visible vertical scrollbar
   (max_lines pins the textarea; long SQL scrolls inside the box) */
#dsk-sql-box textarea {
    overflow-y: auto !important;
    scrollbar-width: thin;
}
/* Keep the SQL input visible while scrolling a long report */
body:has(.st-scroll-page) .dsk-input-col {
    position: sticky !important;
    top: 12px !important;
    align-self: flex-start !important;
}
/* Report as a card (mirrors .sr-report-card) */
.gradio-container .dsk-report-card {
    border: 1px solid #e5e7eb !important;
    border-radius: 10px !important;
    background: #fff !important;
    padding: 14px 18px !important;
    min-height: 320px !important;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.04) !important;
}
.dsk-report-card h1 { margin-top: 0 !important; font-size: 1.35rem !important; }
.dsk-report-card h2 { margin: 16px 0 6px !important; }
.dsk-report-card h3 { margin: 14px 0 6px !important; }
.dsk-report-card table {
    width: 100% !important;
    border-collapse: collapse !important;
    margin: 6px 0 !important;
}
.dsk-report-card th, .dsk-report-card td {
    border: 1px solid #e5e7eb !important;
    padding: 6px 10px !important;
    text-align: left !important;
    vertical-align: top !important;
    line-height: 1.5 !important;
}
.dsk-report-card th { background: #f3f4f6 !important; }
.dsk-report-card tbody tr:nth-child(even) td { background: #fafafa !important; }

/* Data Comparison keeps the fixed sidebar+main layout, so the page itself
   cannot scroll — let the main result panel scroll internally instead.
   The .st-main class is repeated to outrank Gradio's auto-prefixed copy of
   the base .st-main rule (.gradio-container-X .contain .st-main, four
   classes): Gradio duplicates custom CSS under that prefix, and the
   prefixed `body:has(...)` variant can never match (body is not inside
   .contain), so without the repetition this override silently loses and
   the result panel gets no scrollbar. */
body:has(.st-dc-page) .st-main.st-main.st-main.st-main {
    overflow-y: auto !important;
    overflow-x: hidden !important;
}

/* ══════════════════════════════════════════════
   Sidebar — Claude-style push layout (Column)
   ══════════════════════════════════════════════ */
/* Page row: sidebar + main side by side. */
.st-page-row {
    display: flex !important;
    flex-direction: row !important;
    position: fixed !important;
    top: 0; left: 0; right: 0; bottom: 0;
    z-index: 100;
    overflow: hidden !important;
    gap: 0 !important;
    padding: 0 !important;
    flex-wrap: nowrap !important;
}
/* Left sidebar column (width adjustable via drag handle, see _SIDEBAR_RESIZE_JS).
   The Data Comparison sidebar is excluded: it has its own width + CSS resize. */
.st-sidebar:not(.st-dc-sidebar) {
    width: var(--st-sidebar-w, 260px) !important;
    min-width: var(--st-sidebar-w, 260px) !important;
    max-width: var(--st-sidebar-w, 260px) !important;
}
.st-sidebar {
    height: 100% !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    background: #f9fafb !important;
    border-right: 1px solid #e5e7eb !important;
    padding: 10px 12px !important;
    flex-shrink: 0 !important;
    gap: 4px !important;
    display: flex !important;
    flex-direction: column !important;
    flex-wrap: nowrap !important;
}
/* Direct children: full-width column layout */
.st-sidebar > * {
    width: 100% !important;
    max-width: 100% !important;
    min-width: 0 !important;
    box-sizing: border-box !important;
    flex-shrink: 0 !important;
    border: none !important;
    box-shadow: none !important;
}
/* Re-allow horizontal layout for Row containers */
.st-sidebar .row,
.st-sidebar .st-sidebar-row,
.st-sidebar .st-filter-actions,
.st-sidebar .st-filter-confirm-row {
    flex-direction: row !important;
    flex-wrap: nowrap !important;
}
/* CheckboxGroup labels: horizontal for checkbox + text */
.st-sidebar .st-table-filter label {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    gap: 0 !important;
}

/* Data Comparison sidebar: wider, user-resizable via right-edge drag,
   horizontal scrollbar when content overflows */
.st-sidebar.st-dc-sidebar {
    /* flex-basis auto lets `width` control the size (Gradio columns default
       to flex-basis 0%, which ignores width and collapses to min-width);
       width stays non-!important so the browser's drag-resize inline style
       can override it */
    flex: 0 0 auto !important;
    width: 720px;
    min-width: 360px !important;
    max-width: 85vw !important;
    resize: horizontal !important;
    overflow-x: auto !important;
    overflow-y: auto !important;
}
.st-sidebar.st-dc-sidebar > * {
    min-width: 640px !important;
}

/* Right main content: fill remaining width, flex column to pin input at bottom.
   flex-wrap MUST be nowrap: Gradio columns default to wrap, and in a
   fixed-height column container any child taller than the viewport gets
   wrapped into a second column to the RIGHT — outside the container, then
   clipped by overflow:hidden. Symptom: tall results (e.g. Compare All)
   render into the DOM but are completely invisible. */
.st-main {
    flex: 1 1 0 !important;
    min-width: 0 !important;
    height: 100% !important;
    max-height: 100% !important;
    overflow: hidden !important;
    padding: 0 !important;
    display: flex !important;
    flex-direction: column !important;
    flex-wrap: nowrap !important;
}
/* Hide Gradio's native sidebar if accidentally present */
.gradio-sidebar { display: none !important; }
/* Drag handle on the sidebar's right edge (appended to .st-page-row by JS) */
.st-sidebar-resize {
    position: absolute !important;
    top: 0 !important;
    bottom: 0 !important;
    left: calc(var(--st-sidebar-w, 260px) - 3px) !important;
    width: 7px !important;
    cursor: col-resize !important;
    z-index: 150 !important;
    background: transparent;
    transition: background 0.15s;
}
.st-sidebar-resize:hover,
.st-sidebar-resize.st-resizing {
    background: rgba(59, 130, 246, 0.35);
}
body.st-sidebar-dragging {
    cursor: col-resize !important;
    user-select: none !important;
}

/* ══════════════════════════
   Lineage page — the global container is 100vh/overflow-hidden,
   so the page provides its own vertical scroll
   ══════════════════════════ */
.st-lin-page, .st-trp-page, .st-imp-page, .st-mig-page, .st-set-page {
    /* the navbar is hidden, so the page owns the full viewport; keep the
       explicit height so the page (not the clipped app root) scrolls */
    height: 100vh !important;
    max-height: 100vh !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    padding: 12px 16px 24px !important;
    box-sizing: border-box !important;
    scrollbar-width: thin;
    scrollbar-gutter: stable;
}
.st-lin-page::-webkit-scrollbar, .st-trp-page::-webkit-scrollbar,
.st-imp-page::-webkit-scrollbar, .st-mig-page::-webkit-scrollbar,
.st-set-page::-webkit-scrollbar { width: 8px; }
.st-lin-page::-webkit-scrollbar-thumb, .st-trp-page::-webkit-scrollbar-thumb,
.st-imp-page::-webkit-scrollbar-thumb, .st-mig-page::-webkit-scrollbar-thumb,
.st-set-page::-webkit-scrollbar-thumb {
    background: #d1d5db;
    border-radius: 4px;
}
.st-lin-page::-webkit-scrollbar-thumb:hover,
.st-trp-page::-webkit-scrollbar-thumb:hover,
.st-imp-page::-webkit-scrollbar-thumb:hover,
.st-mig-page::-webkit-scrollbar-thumb:hover,
.st-set-page::-webkit-scrollbar-thumb:hover { background: #9ca3af; }
/* Panels grow with their content (e.g. the expanded Hive advanced
   accordion); the page scrollbar above is the only vertical scroll. */
.st-lin-side, .st-lin-main, .st-trp-side, .st-trp-main,
.st-imp-side, .st-imp-main, .st-mig-side, .st-mig-main, .st-set-main {
    height: auto !important;
    max-height: none !important;
    overflow: visible !important;
    align-self: flex-start !important;
}
.st-lin-side, .st-trp-side, .st-imp-side, .st-mig-side {
    padding-right: 6px !important;
    border-right: 1px solid #e5e7eb;
}
/* Settings page stacks blocks directly in the page column; stop flex from
   shrinking them below content height so the page scrollbar can take over. */
.st-set-page > * {
    flex-shrink: 0 !important;
}
.st-set-page {
    max-width: 900px;
    margin: 0 auto !important;
}
.st-lin-hidden {
    display: none !important;
}

/* ══════════════════════════
   Hub landing page — "The Almanac"
   Newspaper-masthead editorial: cream paper, hairline ink rules,
   a giant letterspaced serif masthead with a red initial, mono
   small-caps metadata rows, borderless newspaper columns separated
   by vertical rules. One accent: deep editorial red.
   ══════════════════════════ */
body:has(#st-hub), body:has(#st-hub) .gradio-container,
body:has(#st-hub) main, body:has(#st-hub) .main {
    background: #f3efe4 !important;
}
.st-hub {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    min-height: 95vh;
    padding: 72px 24px 24px;  /* clears the 48px masthead bar */
    position: relative;
    background: #f3efe4;
    color: #3c372e;
}
.st-hub-grid, .st-hub-section-title,
.st-hub-filter-row, .st-hub-footer {
    width: min(1080px, 100%);
}
/* the masthead spans the full content width, centered like a front page */
.st-hub-header {
    width: min(1080px, 100%);
    text-align: center;
}
/* 48px top bar: brand / back link on the left, language select on the right */
.st-hub-topbar {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0 24px;
    border-bottom: 1px solid #1a1613;
}
.st-hub-brand {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 11px;
    font-weight: 700;
    color: #1a1613;
    letter-spacing: 0.18em;
    text-transform: uppercase;
}
.st-hub-ver {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 9px;
    color: #8a8378;
    margin-left: 10px;
    letter-spacing: 0.12em;
}
.st-hub-topbar-right {
    display: flex;
    align-items: center;
    gap: 14px;
}
/* top-bar controls: quiet small-caps, red on hover — newsprint chrome */
.st-hub-gear {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 30px;
    height: 30px;
}
.st-hub-gear svg { width: 14px; height: 14px; fill: #1a1613; }
.st-hub-gear:hover svg { fill: #9e2b25; }
.st-hub-lang-row select {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 10px;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    padding: 4px 20px 4px 6px;
    border: none;
    border-radius: 0;
    background: transparent;
    color: #1a1613;
    height: 30px;
    cursor: pointer;
    outline: none;
}
.st-hub-lang-row select:hover { color: #9e2b25; }
/* masthead block */
.st-hub-header { margin-bottom: 40px; }
.st-hub-health {
    display: inline-flex;
    align-items: center;
    margin-top: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 10px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #6e6757;
}
/* gradio prose styles recolor nested spans — force inheritance */
.st-hub-health span:not(.st-dot) { color: inherit; }
.st-hub-health .st-hub-ok, .st-hub-health .st-hub-ok span:not(.st-dot) {
    color: #1a1613;
}
.st-hub-seg { display: inline-flex; align-items: center; }
.st-hub-seg + .st-hub-seg {
    margin-left: 16px;
    padding-left: 16px;
    border-left: 1px solid #c8c0ad;
}
.st-hub-health code {
    font-family: inherit;
    font-size: 10px;
    background: transparent;
    color: #1a1613;
    padding: 0 0 0 4px;
}
/* status markers: 4px typographic squares — ink when fine, red when not */
.st-dot {
    display: inline-block;
    width: 4px;
    height: 4px;
    border: 1px solid #1a1613;
    border-radius: 0;
    margin-right: 6px;
    flex: none;
}
.st-dot-ok  { background: #1a1613; }
.st-dot-bad { background: #9e2b25; border-color: #9e2b25; }
.st-dot-off { background: transparent; }
.st-hub-ok { color: #1a1613; font-weight: 600; }
.st-hub-bad { color: #9e2b25; font-weight: 700; text-decoration: none; }
a.st-hub-bad:hover { text-decoration: underline; }
.st-hub-dim { color: #8a8378; }
/* the masthead: huge letterspaced serif, red initial, framed by rules */
.st-hub-title {
    /* flourished italic display serif; CJK falls through to SimSun */
    font-family: 'Playfair Display', Didot, 'Bodoni MT', Georgia,
                 'SimSun', '宋体', serif;
    /* sized to set the masthead on a single line at the 1080px measure */
    font-size: clamp(28px, 4.1vw, 56px);
    font-weight: 800;
    font-style: italic;
    text-transform: uppercase;
    white-space: nowrap;
    color: #1a1613;
    letter-spacing: 0.1em;
    line-height: 1.05;
    border-top: 1px solid #1a1613;
    padding-top: 18px;
}
/* the red letters are explicit spans so multi-letter marks (e.g. "AI")
   can carry the accent, not just the first glyph */
.st-hub-title .st-red { color: #9e2b25; }
.st-hub-subtitle {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 0.3em;
    color: #3c372e;
    margin-top: 14px;
    padding: 9px 0;
    border-top: 1px solid #1a1613;
    border-bottom: 1px solid #1a1613;
}
.st-hub-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0 0;
    align-items: stretch;  /* column rules run the full row height */
}
@media (max-width: 860px) {
    .st-hub-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
/* numbering runs continuously across the whole page (01…NN) */
.st-hub { counter-reset: hubcard; }
/* borderless newspaper columns: a heavy rule on top of each entry,
   hairline rules between columns, no boxes, no shadows */
.st-hub-card {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    text-align: left;
    padding: 14px 18px 18px;
    background: transparent !important;
    border: none;
    border-top: 2px solid #1a1613;
    border-radius: 0;
    text-decoration: none !important;
    transition: background .12s;
    cursor: pointer;
    position: relative;
    counter-increment: hubcard;
}
.st-hub-card:nth-child(3n+1) { padding-left: 0; }
.st-hub-card:not(:nth-child(3n+1)) { border-left: 1px solid #c8c0ad; }
.st-hub-card:hover { background: #ece7d7 !important; }
/* folio number, set quietly in the top corner */
.st-hub-card::after {
    content: "NO. " counter(hubcard, decimal-leading-zero);
    position: absolute;
    top: 16px;
    right: 10px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 9px;
    letter-spacing: 0.12em;
    color: #8a8378;
    transition: color .12s;
}
.st-hub-card:hover::after { color: #9e2b25; }
/* no inline icons in a newspaper column — the folio corner is enough */
.st-hub-logo { display: none; }
.st-hub-card-title {
    font-family: Georgia, 'Times New Roman', 'SimSun', '宋体', serif;
    font-size: 17px;
    font-weight: 700;
    color: #1a1613;
    letter-spacing: 0;
    padding-right: 52px;  /* keep clear of the folio number */
}
.st-hub-card:hover .st-hub-card-title { color: #9e2b25; }
/* clickability hint lives on the whole card: arrow appears next to the
   title on hover instead of a repeated "Enter →" footer */
.st-hub-card-title::after {
    content: " →";
    opacity: 0;
    color: #9e2b25;
    transition: opacity .12s;
}
.st-hub-card:hover .st-hub-card-title::after { opacity: 1; }
.st-hub-zh {
    font-size: 11px;
    font-weight: 500;
    color: #9ca3af;
}
.st-hub-card-desc {
    grid-column: 1 / -1;
    grid-row: 2;
    margin-top: 9px;
    font-family: Georgia, 'Times New Roman', 'SimSun', '宋体', serif;
    font-size: 12.5px;
    color: #3c372e;
    line-height: 20px;
    min-height: 40px;  /* always two lines — no ragged card bottoms */
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
/* the per-card "Enter →" footer is markup noise — hidden everywhere; the
   whole card is the link and the hover arrow on the title says so */
.st-hub-enter { display: none; }
.st-dim-hint, .st-dim-hint p { font-size: 11px !important; color: #9ca3af !important; }
/* section label: a small-caps kicker above its column block */
.st-hub-section-title {
    margin: 34px 0 10px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.22em;
    text-transform: uppercase;
    text-align: left;
    color: #9e2b25;
}
.st-hub-section-title:first-of-type { margin-top: 10px; }
.st-hub-filter-row { margin-bottom: 4px; }
/* colophon: a double rule closes the page, folio mark on the right */
.st-hub-footer {
    margin-top: auto;
    padding-top: 12px;
    border-top: 3px double #1a1613;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 10px;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: #6e6757;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
}
.st-hub-footer a { color: #1a1613; text-decoration: none; font-weight: 700; }
.st-hub-footer a:hover { color: #9e2b25; }
.st-hub-mark {
    font-family: Georgia, 'Times New Roman', 'SimSun', '宋体', serif;
    font-style: italic;
    font-weight: 700;
    font-size: 15px;
    letter-spacing: 0.02em;
    text-transform: none;
    color: #9e2b25;
    user-select: none;
}
.st-hub-landing-sec { margin-top: 30px; }  /* left-aligned to the grid edge */
.st-hub-filter-wrap {
    position: relative;
    display: inline-block;
    width: min(348px, 100%);
}
.st-hub-filter-ico {
    position: absolute;
    left: 4px;
    top: 50%;
    transform: translateY(-50%);
    pointer-events: none;
    display: flex;
}
.st-hub-filter-ico svg { width: 13px; height: 13px; fill: #1a1613; }
.st-hub-filter-kbd {
    position: absolute;
    right: 4px;
    top: 50%;
    transform: translateY(-50%);
    pointer-events: none;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 10px;
    font-weight: 700;
    color: #1a1613;
    padding: 0 5px;
    background: transparent;
    border: 1px solid #1a1613;
}
/* classified-ad search: an underline, not a box */
#st-hub-filter {
    width: 100%;
    height: 32px;
    padding: 0 30px 0 26px;
    border: none;
    border-bottom: 2px solid #1a1613;
    border-radius: 0;
    font-size: 12px;
    background: transparent;
    color: #1a1613;
    outline: none;
}
#st-hub-filter::placeholder {
    color: #8a8378;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    text-transform: uppercase;
    letter-spacing: 0.14em;
    font-size: 10px;
}
#st-hub-filter:focus { border-bottom-color: #9e2b25; }
.st-hub-back {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.18em;
    text-transform: uppercase;
    color: #1a1613;
    text-decoration: none !important;
}
.st-hub-back:hover { color: #9e2b25; }
/* ══════════════════════════════════════════
   Chatbot — fill remaining height exactly
   ══════════════════════════════════════════ */
.st-chatbot {
    border: none !important;
    background: #fff !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    overflow-y: auto !important;
    padding: 0 !important;
    margin: 0 !important;
    flex: 1 1 0 !important;
    min-height: 0 !important;
}
.st-chart {
    max-height: 280px !important;
    overflow: hidden !important;
    flex: none !important;
}
.st-chart img, .st-chart canvas, .st-chart svg {
    max-height: 260px !important;
    width: auto !important;
    margin: 0 auto !important;
    display: block !important;
}
.st-chatbot .message {
    font-size: 11px !important;
    line-height: 1.6 !important;
    padding: 6px 20px !important;
}
/* ── User message: right-aligned with left space ── */
.st-chatbot .user-row {
    margin-left: 22% !important;
    margin-top: 14px !important;
    margin-bottom: 14px !important;
    background: #fff7ed !important;
    border: 1px solid #fed7aa !important;
    border-radius: 16px 16px 4px 16px !important;
    padding: 8px 14px !important;
}
.st-chatbot .user-row .message {
    padding: 0 !important;
}
.st-chatbot .message code {
    font-size: 10px !important;
    background: #f3f4f6 !important;
    padding: 1px 4px !important;
    border-radius: 3px !important;
}
.st-chatbot .message pre {
    background: #1e1e2e !important;
    color: #cdd6f4 !important;
    padding: 8px 12px !important;
    border-radius: 6px !important;
    font-size: 10px !important;
    margin: 4px 0 !important;
    overflow-x: auto !important;
}

/* ── Inline download buttons inside chat messages ── */
.st-dl-btns {
    display: flex;
    gap: 8px;
    margin-top: 8px;
    flex-wrap: wrap;
}
.st-dl-btns a:hover {
    background: var(--background-fill-primary, #eee) !important;
}

/* ── Placeholder (empty state) ── */
.st-empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 16px 30px;
    color: #6b7280;
}
.st-empty-logo {
    font-size: 22px;
    font-weight: 800;
    background: #f76707;
    color: #fff;
    width: 44px;
    height: 44px;
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-bottom: 16px;
    letter-spacing: -1px;
}
.st-empty-title {
    font-size: 16px;
    font-weight: 600;
    color: #1f2937;
    margin-bottom: 20px;
}
.st-empty-hints {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: center;
    max-width: 540px;
}
.st-hint-card {
    padding: 9px 14px;
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 8px;
    font-size: 13px;
    color: #4b5563;
    cursor: pointer;
    transition: border-color .15s;
}
.st-hint-card:hover {
    border-color: #f76707;
    color: #f76707;
}

.st-connect-btn {
    width: 100% !important;
    border-radius: 8px !important;
    margin-top: 2px !important;
}
.st-sidebar-row {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: nowrap !important;
    gap: 6px !important;
    width: 100% !important;
}
.st-sidebar-row > * {
    flex: 1 !important;
    min-width: 0 !important;
}
/* Fix Dropdown arrow blown up by sidebar flex overrides */
.st-sidebar svg[class*="dropdown-arrow"] {
    width: 18px !important;
    height: 18px !important;
    min-width: 18px !important;
    min-height: 18px !important;
    max-width: 18px !important;
    max-height: 18px !important;
}
.st-sidebar [class*="icon-wrap"] {
    width: auto !important;
    min-width: 0 !important;
    max-width: none !important;
    flex-shrink: 0 !important;
}
.st-sidebar [class*="secondary-wrap"] {
    flex-direction: row !important;
    align-items: center !important;
    width: 100% !important;
}
.st-filter-accordion {
    margin-top: 4px !important;
    overflow: hidden !important;
    width: 100% !important;
}
.st-filter-accordion [class*="label-wrap"] {
    padding: 4px 8px !important;
    min-height: 0 !important;
    font-size: 12px !important;
    line-height: 1.3 !important;
    background: #f9fafb !important;
    border: none !important;
    box-shadow: none !important;
    gap: 4px !important;
}
.st-filter-accordion [class*="label-wrap"] span {
    font-size: 12px !important;
    font-weight: 500 !important;
    line-height: 1.3 !important;
}
.st-filter-accordion [class*="label-wrap"] span[class*="icon"] {
    font-size: 10px !important;
}
.st-table-search textarea {
    width: 100% !important;
    font-size: 12px !important;
    padding: 4px 8px !important;
    min-height: 28px !important;
    border-radius: 6px !important;
}
.st-table-search { margin-bottom: 2px !important; }
.st-table-filter {
    width: 100% !important;
    max-height: 200px !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
    border: 1px solid #f0f0f0 !important;
    border-radius: 6px !important;
    padding: 4px 6px !important;
}
.st-table-filter .wrap {
    flex-direction: column !important;
    flex-wrap: nowrap !important;
    gap: 1px !important;
    width: 100% !important;
}
.st-table-filter label {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    min-width: 0 !important;
    font-size: 12px !important;
    line-height: 1.5 !important;
    padding: 2px 0 !important;
    cursor: pointer !important;
}
.st-table-filter label span {
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    white-space: nowrap !important;
    min-width: 0 !important;
}
.st-table-filter label:hover { background: #f5f5f5 !important; border-radius: 4px !important; }
.st-table-filter input[type="checkbox"] {
    width: 14px !important; height: 14px !important;
    min-width: 14px !important;
    flex-shrink: 0 !important;
    margin-right: 6px !important;
}
.st-filter-actions {
    gap: 4px !important;
    flex-wrap: nowrap !important;
}
.st-filter-act-btn {
    font-size: 11px !important;
    padding: 2px 6px !important;
    min-width: 0 !important;
    border-radius: 4px !important;
    flex: 1 !important;
}
.st-filter-confirm-row {
    gap: 4px !important;
    margin-top: 2px !important;
    flex-wrap: nowrap !important;
}
.st-filter-confirm-btn, .st-filter-cancel-btn {
    font-size: 12px !important;
    padding: 4px 10px !important;
    border-radius: 6px !important;
    min-width: 0 !important;
    flex: 1 !important;
}
.st-sidebar-control label {
    font-size: 10px !important;
    font-weight: 600 !important;
    color: #6b7280 !important;
}
.st-sidebar-control input,
.st-sidebar-control select { font-size: 10px !important; }
.st-sidebar-status input { font-size: 10px !important; }

/* ── Top bar with language switcher ── */
.st-topbar-row,
.st-topbar-row.row {
    display: flex !important;
    flex-direction: row !important;
    align-items: center !important;
    justify-content: flex-end !important;
    padding: 6px 16px !important;
    margin: 0 !important;
    gap: 8px !important;
    min-height: 36px !important;
    max-height: 36px !important;
    height: 36px !important;
    flex: 0 0 36px !important;
    background: #fff !important;
    border-bottom: 1px solid #f0f0f0 !important;
    overflow: visible !important;
    flex-wrap: nowrap !important;
}
.st-topbar-spacer {
    flex: 1 !important;
}
/* ── Home button in topbar ── */
.st-home-btn {
    min-width: 32px !important;
    max-width: 32px !important;
    height: 28px !important;
    padding: 0 !important;
    font-size: 14px !important;
    border-radius: 6px !important;
    border: 1px solid #e5e7eb !important;
    background: #f9fafb !important;
    cursor: pointer !important;
    flex-shrink: 0 !important;
}
.st-home-btn:hover {
    border-color: #f76707 !important;
    background: #fff7ed !important;
}
/* workspace back-button injected by lang_pref.STAMP_JS next to the 🏠 —
   deliberately smaller and quieter than the page content around it */
.st-ws-btn {
    height: 20px !important;
    line-height: 18px !important;
    padding: 0 6px !important;
    font-size: 10px !important;
    color: #6b7280;
    border-radius: 5px;
    border: 1px solid #e5e7eb;
    background: #f9fafb;
    cursor: pointer;
    white-space: nowrap;
    flex-shrink: 0;
    align-self: center;
    margin-right: 6px;
    min-width: 0 !important;
    width: fit-content !important;
    max-width: fit-content !important;
    flex: 0 0 auto !important;
}
.st-ws-btn:hover {
    border-color: #f76707;
    color: #f76707;
    background: #fff7ed;
}

/* ── History / Favorites page ── */
.st-history-page {
    padding: 16px 28px !important;
    max-width: 1400px !important;
    margin: 0 auto !important;
    overflow: visible !important;
    height: auto !important;
}
.st-history-page h2 {
    font-size: 16px !important;
    font-weight: 700 !important;
    color: #111827 !important;
    margin: 0 0 4px !important;
}
.st-hist-toolbar {
    gap: 6px !important;
    margin-bottom: 6px !important;
}
.st-hist-btn {
    min-width: 0 !important;
    padding: 3px 10px !important;
    font-size: 11px !important;
    border-radius: 6px !important;
}
.st-hist-sel-info {
    min-height: 0 !important;
    margin: 0 0 2px !important;
}
.st-hist-sel-info p {
    font-size: 11px !important;
    color: #6b7280 !important;
    margin: 0 !important;
}
.st-fav-search-row { margin-bottom: 4px !important; }
.st-fav-rename-row { margin-bottom: 4px !important; }
.st-fav-table,
.st-hist-table {
    overflow: visible !important;
}
.st-fav-table > div,
.st-hist-table > div,
.st-history-page .wrap,
.st-history-page .table-wrap {
    overflow: visible !important;
    max-height: none !important;
}
.st-history-page table {
    font-size: 12px !important;
    width: 100% !important;
    border-collapse: collapse !important;
}
.st-history-page th {
    font-size: 11px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.3px !important;
    color: #9ca3af !important;
    background: #f9fafb !important;
    padding: 6px 10px !important;
    white-space: nowrap !important;
    border-bottom: 2px solid #e5e7eb !important;
    position: sticky !important;
    top: 0 !important;
    z-index: 2 !important;
}
.st-history-page td {
    padding: 6px 10px !important;
    border-bottom: 1px solid #f3f4f6 !important;
    vertical-align: top !important;
    line-height: 1.4 !important;
    color: #374151 !important;
}
.st-history-page tr:hover td {
    background: #f0f7ff !important;
    cursor: pointer;
}
.st-history-page td:nth-child(1) {
    color: #9ca3af !important;
    font-size: 11px !important;
}
.st-history-page td:nth-child(2) {
    color: #6b7280 !important;
    font-size: 11px !important;
    white-space: nowrap !important;
}

/* ── SQL column: show full text, wrap naturally ── */
.st-fav-table td:nth-child(4),
.st-hist-table td:nth-child(6) {
    font-family: 'SF Mono', 'Consolas', 'Monaco', monospace !important;
    font-size: 11px !important;
    color: #6b7280 !important;
    white-space: pre-wrap !important;
    word-break: break-word !important;
}

/* ── Hide Gradio block borders inside history/favorites pages ── */
.st-history-page > *,
.st-history-page > * > *,
.st-history-page [class*="block"],
.st-history-page [class*="panel"],
.st-history-page [class*="form"],
.st-history-page [class*="padded"] {
    border: none !important;
    box-shadow: none !important;
}
.st-history-page h3 {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: #374151 !important;
    margin: 8px 0 4px !important;
}

/* ── Responsive sizing ── */
button { font-size: 10px !important; }
label { font-size: 10px !important; }

"""
