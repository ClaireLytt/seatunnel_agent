"""Gradio page adapter for the Data Comparison page.

Every selector in the whole test framework lives in this file — nothing else
is allowed to touch the DOM directly.  The locator strategies encode Gradio 6
behaviors verified against this repo:

1. ``gr.Textbox`` renders a ``<textarea>``, not ``<input>``.
2. Dropdowns are ``<input aria-expanded>`` + ``ul[role=listbox] li``.
3. ``wait_until="networkidle"`` never fires (SSE keeps a connection open) —
   always ``domcontentloaded`` plus explicit waits.
4. Typing fires ``.input``; programmatic ``fill("")`` does not — ``clear``
   therefore uses real keystrokes (Ctrl+A, Backspace).
5. A dropdown input with content natively filters the option list — read the
   full option set only after clearing it.
"""

from __future__ import annotations

from playwright.sync_api import Locator, Page

# ── zh/en label table ──
# Key = the "human name" used in YAML cases (Chinese, matching the manual
# checklist); values = (zh, en) label texts as rendered, straight from
# data_comparison/i18n.py.  Extend here (only here) when migrating cases.
LABELS: dict[str, tuple[str, ...]] = {
    # connection panel
    "数据源类型": ("数据源类型", "Data Source"),
    "主机":       ("主机地址", "Host"),
    "端口":       ("端口", "Port"),
    "数据库":     ("数据库", "Database"),
    "用户名":     ("用户名", "Username"),
    "密码":       ("密码", "Password"),
    "连接":       ("连接", "Connect"),
    "状态":       ("状态", "Status"),
    "选择表":     ("选择表", "Select Table"),
    # compare buttons
    "结构对比":   ("结构对比", "Schema Diff"),
    "行数对比":   ("行数对比", "Row Count"),
    "样本数据":   ("样本数据", "Sample Data"),
    "聚合对比":   ("聚合对比", "Aggregates"),
    "全部对比":   ("全部对比", "Compare All"),
    "批量行数":   ("批量行数", "Batch Count"),
    "字段画像":   ("字段画像", "Column Profile"),
    "批量全量对比": ("批量全量对比", "Batch Full Compare"),
    # shared filter inputs
    "WHERE":      ("WHERE 条件", "WHERE"),
    "阈值":       ("阈值", "Threshold"),
    "主键列":     ("主键列", "Key Column(s)"),
    "字段映射":   ("字段映射", "Column Mapping"),
    "采样方式":   ("采样方式", "Sampling"),
    "分组列":     ("分组列", "Group Column"),
    "启用脱敏":   ("启用脱敏", "Enable masking"),
    # accordions + their controls
    "预设":       ("预设", "Presets"),
    "预设名称":   ("预设名称", "Preset Name"),
    "环境":       ("环境", "Environment"),
    "保存预设 (A)": ("保存预设 (A)", "Save Preset (A)"),
    "保存预设 (B)": ("保存预设 (B)", "Save Preset (B)"),
    "加载预设 (A)": ("加载预设 (A)", "Load Preset (A)"),
    "加载预设 (B)": ("加载预设 (B)", "Load Preset (B)"),
    "增量对比":   ("增量对比", "Incremental"),
    "水位线列":   ("水位线列", "Watermark Column"),
    "上次值":     ("上次值", "Last Value"),
    "质量规则":   ("质量规则", "Quality Rules"),
    "规则":       ("规则", "Rules"),
    "质量检查":   ("质量检查", "Check Quality"),
    "数据倾斜":   ("数据倾斜", "Data Skew"),
    "倾斜分析列": ("倾斜分析列", "Skew Column"),
    "分析倾斜":   ("分析倾斜", "Analyze Skew"),
    "校验和":     ("校验和", "Checksum"),
    "校验和对比": ("校验和对比", "Compare Checksum"),
    "分区比对":   ("分区比对", "Partition"),
    "分区列":     ("分区列", "Partition Column"),
    "对比分区":   ("对比分区", "Compare Partitions"),
    "自定义聚合": ("自定义聚合", "Custom Aggregates"),
    "比对自定义聚合": ("比对自定义聚合", "Compare Custom Agg"),
    "自定义 SQL": ("自定义 SQL", "Custom SQL"),
    "SQL (A)":    ("SQL (A)",),
    "SQL (B)":    ("SQL (B)",),
    "SQL 对比":   ("SQL 对比", "Compare SQL"),
    "生成同步配置": ("生成同步配置", "Generate Sync Config"),
    "生成差异 SQL": ("生成差异 SQL", "Generate Diff SQL"),
    "模板":       ("模板", "Templates"),
    "模板名称":   ("模板名称", "Template Name"),
    "保存模板":   ("保存模板", "Save Template"),
    "加载模板":   ("加载模板", "Load Template"),
    "批量模板":   ("批量模板", "Batch Templates"),
    "运行选中":   ("运行选中", "Run Selected"),
    "定时任务":   ("定时任务", "Schedule"),
    "间隔":       ("间隔（分钟）", "Interval (min)"),
    "启动定时":   ("启动定时", "Start Schedule"),
    "停止定时":   ("停止定时", "Stop Schedule"),
    "Webhook 通知": ("Webhook 通知", "Webhook"),
    "Webhook URL": ("Webhook URL",),
    "仅失败时通知": ("仅失败时通知", "Notify on failure only"),
    "趋势":       ("趋势", "Trends"),
    "告警规则":   ("告警规则", "Alert Rules"),
    "对比趋势":   ("对比趋势", "Comparison Trends"),
    "旧报告":     ("旧报告", "Old Report"),
    "新报告":     ("新报告", "New Report"),
    "对比报告":   ("对比报告", "Compare Reports"),
    "上游依赖":   ("上游依赖", "Upstream Dependencies"),
    "环境 A":     ("环境 A", "Env A"),
    "环境 B":     ("环境 B", "Env B"),
    "跨环境对比": ("跨环境对比", "Compare Environments"),
    "导出 CSV":   ("导出 CSV", "Export CSV"),
    "导出 Excel": ("导出 Excel", "Export Excel"),
    "查看报告":   ("查看报告", "View Report"),
    "保存报告":   ("保存报告", "Save Report"),
    "加载报告":   ("加载报告", "Load Report"),
    "血缘SQL":    ("用于溯源的SQL语句（每行一条）",
                   "SQL statements to trace lineage from (one per line)"),
    # ── SQL Review page (/sqlreview) ──
    "SQL":        ("SQL",),
    "开始审查":   ("开始审查", "Start Review"),
    "生成修复 SQL": ("生成修复 SQL（LLM）", "Generate Fixed SQL (LLM)"),
    "清空":       ("清空", "Clear"),
    "下载报告":   ("下载报告（.md）", "Download Report (.md)"),
    "SQL 方言":   ("SQL 方言", "SQL Dialect"),
    "审查模式":   ("审查模式", "Review Mode"),
    "表结构 DDL": ("表结构 DDL（可选，用于 schema 校验）",
                   "Table DDL (optional, for schema checks)"),
    "DDL 输入":   ("CREATE TABLE 语句", "CREATE TABLE statements"),
    "审查规则":   ("规则配置（可选，.sqlreview.yaml 格式）",
                   "Rule config (optional, .sqlreview.yaml format)"),
    "规则输入":   ("YAML 规则", "YAML rules"),
    # ── Lineage page (/lineage) ──
    "SQL 目录":   ("SQL 目录", "SQL directory"),
    "SeaTunnel 配置目录": ("SeaTunnel 配置目录", "SeaTunnel config directory"),
    "构建血缘图": ("构建血缘图", "Build lineage graph"),
    "目标表":     ("目标表", "Target table"),
    "查询血缘":   ("查询血缘", "Query lineage"),
    "表名搜索":   ("表名搜索", "Table search"),
    "搜索":       ("搜索", "Search"),
    "治理体检":   ("治理体检", "Governance health check"),
    "血缘字段":   ("字段（可选）", "Column (optional)"),
    "查询路径":   ("查询路径", "Find path"),
    "SLA 影响分析": ("SLA 影响分析", "SLA impact analysis"),
    "保存快照":   ("保存快照", "Save snapshot"),
    "快照对比":   ("快照对比", "Compare snapshots"),
    "路径终点表": ("路径终点表", "Path destination table"),
    "快照名":     ("快照名（可选）", "Snapshot name (optional)"),
    "对比快照":   ("对比快照", "Compare against snapshot"),
}


def _texts(name: str) -> tuple[str, ...]:
    return LABELS.get(name, (name,))


class DCPage:
    """Adapter for the Data Comparison page.  side: 'A' | 'B' | None (global)."""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base = base_url.rstrip("/")

    # ── navigation & regions ──

    # per-route "page is ready" selector (default: body)
    READY = {
        "/datacompare": ".st-dc-sidebar",
        "/sqlreview": "#sr-sql-box textarea",
        "/lineage": ".st-lin-side",
        "/text2sql": ".st-sidebar-status",
    }

    def goto(self, path: str = "/datacompare") -> None:
        self.page.goto(self.base + path, wait_until="domcontentloaded")
        self.page.wait_for_selector(self.READY.get(path, "body"),
                                    timeout=20_000)

    def _panel(self, side: str | None) -> Locator:
        """A/B connection panel; None = whole page.

        The two panels are the columns of the first Row inside the sidebar —
        identified robustly as the ancestor columns of the two status boxes.
        """
        if side is None:
            return self.page.locator("body")
        if not self.page.locator(".st-dc-sidebar").count():
            # pages without the A/B layout (e.g. /text2sql): whole page
            return self.page.locator("body")
        idx = 0 if str(side).upper() == "A" else 1
        return (self.page
                .locator(".st-dc-sidebar .st-sidebar-status")
                .nth(idx)
                .locator("xpath=ancestor::div[contains(@class,'column')][1]"))

    def _scope(self, side: str | None) -> Locator:
        """Search scope: a panel for A/B, else the whole sidebar + main."""
        return self._panel(side) if side else self.page.locator("body")

    # ── locator chain: label → placeholder → button text ──

    def textbox(self, name: str, side: str | None = None) -> Locator:
        scope = self._scope(side)
        for text in _texts(name):
            # Gradio 6: <label><span data-testid="block-info">Label</span>
            #           ...<textarea>  (single-line Textbox is still textarea)
            loc = scope.locator(
                f"label:has(span:text-is('{text}'))").locator(
                "textarea, input[type='text'], input[type='password']")
            if loc.count():
                return loc.first
            loc = scope.locator(f"textarea[placeholder='{text}']")
            if loc.count():
                return loc.first
        raise LookupError(f"textbox not found: {name} (side={side})")

    def button(self, name: str, side: str | None = None) -> Locator:
        """Action button by visible text.  Accordion headers are <button>
        too and may carry the same text (e.g. 生成同步配置) — skip them."""
        scope = self._scope(side)
        for text in _texts(name):
            loc = scope.locator(
                f"button:text-is('{text}'):not(.label-wrap)")
            if loc.count():
                return loc.first
        for text in _texts(name):
            loc = scope.locator(
                f"button:has-text('{text}'):not(.label-wrap)")
            if loc.count():
                return loc.first
        raise LookupError(f"button not found: {name} (side={side})")

    def dropdown_input(self, name: str, side: str | None = None) -> Locator:
        scope = self._scope(side)
        for text in _texts(name):
            # Gradio 6 dropdowns carry the label as aria-label on the input
            loc = scope.locator(f"input[aria-label='{text}']")
            if loc.count():
                return loc.first
            loc = scope.locator(
                f"label:has(span:text-is('{text}'))").locator("input")
            if loc.count():
                return loc.first
        raise LookupError(f"dropdown not found: {name} (side={side})")

    def _pick_listbox_item(self, value: str) -> None:
        """Click the listbox item whose normalized text equals *value*.

        The currently-selected item renders as '✓\\n<value>', so a plain
        :text-is() misses it."""
        items = self.page.locator("ul[role='listbox'] li")
        items.first.wait_for(state="visible", timeout=5_000)
        n = items.count()
        for i in range(n):
            txt = items.nth(i).inner_text().strip().lstrip("✓").strip()
            if txt == value:
                items.nth(i).click()
                return
        seen = [items.nth(i).inner_text().strip().lstrip("✓").strip()
                for i in range(n)]
        raise LookupError(f"listbox item not found: {value!r} (visible: {seen})")

    def checkbox(self, name: str, side: str | None = None) -> Locator:
        scope = self._scope(side)
        for text in _texts(name):
            loc = scope.locator(
                f"label:has-text('{text}') input[type='checkbox']")
            if loc.count():
                return loc.first
        raise LookupError(f"checkbox not found: {name} (side={side})")

    # ── actions ──

    def click_button(self, name: str, side: str | None = None) -> None:
        self.button(name, side).click()

    def clear_box(self, name: str, side: str | None = None) -> None:
        """Clear with real keystrokes so Gradio's .input event fires."""
        box = self.textbox(name, side)
        box.click()
        self.page.keyboard.press("Control+a")
        self.page.keyboard.press("Backspace")

    def clear_and_type(self, name: str, value: str,
                       side: str | None = None) -> None:
        self.clear_box(name, side)
        if value:
            self.textbox(name, side).type(str(value), delay=15)

    def press_in(self, keys: str, in_box: str | None = None,
                 side: str | None = None) -> None:
        if in_box:
            self.textbox(in_box, side).click()
        self.page.keyboard.press(keys)

    def select_ds(self, value: str, side: str = "A") -> None:
        """Data-source type dropdown: exact label match from a fixed list."""
        inp = self.dropdown_input("数据源类型", side)
        inp.click()
        self._pick_listbox_item(value)
        # ds change round-trips to the server to toggle host/port visibility
        # and refresh placeholders (~1s measured)
        self.page.wait_for_timeout(1_500)

    def dropdown_type(self, name: str, text: str,
                      side: str | None = None) -> None:
        """Type filter text into a dropdown without selecting anything."""
        inp = self.dropdown_input(name, side)
        inp.click()
        self.page.keyboard.press("Control+a")
        self.page.keyboard.press("Backspace")
        if text:
            inp.type(str(text), delay=25)
        self.page.wait_for_timeout(400)          # let the option list settle

    def dropdown_options(self, name: str, side: str | None = None,
                         keep_filter: bool = False) -> list[str]:
        """Currently visible options.  Unless *keep_filter*, clears the input
        first (a filtered input hides options — gotcha #5)."""
        inp = self.dropdown_input(name, side)
        if not keep_filter:
            inp.click()
            self.page.keyboard.press("Control+a")
            self.page.keyboard.press("Backspace")
        elif not inp.get_attribute("aria-expanded") == "true":
            inp.click()
        self.page.wait_for_timeout(400)
        items = self.page.locator("ul[role='listbox'] li")
        vals = []
        for i in range(items.count()):
            txt = items.nth(i).inner_text().strip()
            vals.append(txt.lstrip("✓").strip())
        self._close_dropdown()
        return vals

    def _close_dropdown(self) -> None:
        """Close an open dropdown by blurring (clicking a neutral spot).

        Escape also closes it, but leaves the input text empty; blur makes
        Gradio restore the selected value — which is what a user sees."""
        self.page.locator(".st-main").first.click(position={"x": 8, "y": 8})
        self.page.wait_for_timeout(200)

    def dropdown_select(self, name: str, value: str,
                        side: str | None = None) -> None:
        """Open dropdown, type the full value (native filter), click the
        exact item."""
        inp = self.dropdown_input(name, side)
        inp.click()
        self.page.keyboard.press("Control+a")
        self.page.keyboard.press("Backspace")
        inp.type(str(value), delay=15)
        self.page.wait_for_timeout(300)
        self._pick_listbox_item(str(value))
        self.page.wait_for_timeout(200)

    def dropdown_select_index(self, name: str, index: int,
                              side: str | None = None) -> str:
        """Pick the nth (0-based) option — for dropdowns whose option texts
        are dynamic (e.g. timestamped report files).  Returns the text."""
        inp = self.dropdown_input(name, side)
        inp.click()
        items = self.page.locator("ul[role='listbox'] li")
        items.first.wait_for(state="visible", timeout=5_000)
        n = items.count()
        if index >= n:
            raise LookupError(f"dropdown '{name}' has {n} options, "
                              f"index {index} out of range")
        text = items.nth(index).inner_text().strip().lstrip("✓").strip()
        items.nth(index).click()
        self.page.wait_for_timeout(200)
        return text

    def select_table(self, value: str, side: str = "A") -> None:
        self.dropdown_select("选择表", value, side)

    def set_checkbox(self, name: str, on: bool,
                     side: str | None = None) -> None:
        box = self.checkbox(name, side)
        if box.is_checked() != on:
            box.click()

    def open_accordion(self, name: str) -> None:
        """Expand an accordion if it's collapsed (idempotent)."""
        for text in _texts(name):
            hdr = self.page.locator(
                f"button.label-wrap:has-text('{text}'), button:has-text('{text}'):has(.icon)")
            for i in range(hdr.count()):
                h = hdr.nth(i)
                cls = h.get_attribute("class") or ""
                if "label-wrap" in cls or h.locator(".icon").count():
                    if "open" not in cls:
                        h.click()
                        self.page.wait_for_timeout(250)
                    return
        # fallback: first matching header-ish button
        for text in _texts(name):
            hdr = self.page.locator(
                f".label-wrap:has-text('{text}')")
            if hdr.count():
                cls = hdr.first.get_attribute("class") or ""
                if "open" not in cls:
                    hdr.first.click()
                    self.page.wait_for_timeout(250)
                return
        raise LookupError(f"accordion not found: {name}")

    def screenshot(self, path: str) -> None:
        self.page.screenshot(path=path, full_page=False)

    # ── waits ──

    def _status_box(self, side: str = "A"):
        idx = 0 if str(side).upper() == "A" else 1
        loc = self.page.locator(".st-dc-sidebar .st-sidebar-status")
        if not loc.count():
            # other pages (e.g. /text2sql) have a single unscoped status box
            loc = self.page.locator(".st-sidebar-status")
            idx = min(idx, max(loc.count() - 1, 0))
        return loc.nth(idx).locator("textarea, input")

    def status_text(self, side: str = "A") -> str:
        return self._status_box(side).input_value()

    def wait_status(self, side: str = "A", ok: bool = True,
                    timeout_ms: int = 20_000) -> str:
        mark = "✅" if ok else "❌"
        handle = self._status_box(side).element_handle()
        self.page.wait_for_function(
            "arg => arg.el.value.includes(arg.mark)",
            arg={"el": handle, "mark": mark}, timeout=timeout_ms)
        return self.status_text(side)

    def result_container(self) -> Locator:
        # data comparison result card; falls back to the SQL review report
        loc = self.page.locator(".st-main .st-schema-card")
        if loc.count():
            return loc.first
        loc = self.page.locator(".st-lin-main")
        if loc.count():
            return loc.first
        loc = self.page.locator(".st-trp-main")
        if loc.count():
            return loc.first
        return self.page.locator(".sr-report-card").last

    def result_text(self) -> str:
        # text_content, not inner_text: result cards hold row previews in
        # collapsed <details> which a user can expand — assertions must see
        # that content too.
        return self.result_container().text_content() or ""

    def result_html(self) -> str:
        return self.result_container().inner_html()

    def wait_result_change(self, before_html: str,
                           timeout_ms: int = 30_000) -> None:
        """Wait until the result area differs from *before_html* AND then
        stays unchanged for 1s (Gradio has no global loading signal).

        Blank content never settles: on slow machines Gradio transiently
        clears the area mid-update, and the stability window must not land
        on that intermediate state (seen as a CI-only flake on X1)."""
        handle = self.result_container().element_handle()
        self.page.wait_for_function(
            """arg => {
                const now = arg.el.innerHTML;
                if (now === arg.before) { window.__uitest_t = 0; return false; }
                if (!arg.el.textContent.trim()) { return false; }
                if (window.__uitest_last !== now) {
                    window.__uitest_last = now;
                    window.__uitest_t = Date.now();
                    return false;
                }
                return (Date.now() - window.__uitest_t) > 1000;
            }""",
            arg={"el": handle, "before": before_html}, timeout=timeout_ms)

    def wait_result_stable(self, timeout_ms: int = 30_000) -> None:
        """Wait until the result HTML is non-blank and unchanged for 1s."""
        handle = self.result_container().element_handle()
        self.page.wait_for_function(
            """arg => {
                const now = arg.el.innerHTML;
                if (!arg.el.textContent.trim()) { return false; }
                if (window.__uitest_last2 !== now) {
                    window.__uitest_last2 = now;
                    window.__uitest_t2 = Date.now();
                    return false;
                }
                return (Date.now() - window.__uitest_t2) > 1000;
            }""",
            arg={"el": handle}, timeout=timeout_ms)

    def wait_for_text(self, text: str, where: str = "body",
                      timeout_ms: int = 15_000) -> None:
        """Poll until *text* appears in the page body (or result area) —
        replaces fragile fixed waits for slow-rendering side effects."""
        target = ("document.body" if where == "body"
                  else "document.querySelector('.st-main .st-schema-card, .st-lin-main, .sr-report-card')")
        self.page.wait_for_function(
            f"t => (({target})?.textContent || '').includes(t)",
            arg=text, timeout=timeout_ms)

    def set_language(self, lang: str = "中文") -> None:
        """Switch UI language via the top-right dropdown.

        The data comparison page marks it .st-lang-dd; the SQL review page
        renders it as the first bare combobox on the page."""
        dd = self.page.locator(".st-lang-dd input")
        if not dd.count():
            dd = self.page.locator("input[role='combobox']")
        dd.first.click()
        self._pick_listbox_item(lang)
        self.page.wait_for_timeout(600)          # i18n re-render

    # ── element state (for visible/hidden asserts) ──

    def is_visible(self, name: str, side: str | None = None) -> bool:
        try:
            el = self.textbox(name, side)
        except LookupError:
            try:
                el = self.button(name, side)
            except LookupError:
                return False
        # Gradio hides components by styling an ancestor .block
        return el.is_visible()

    # ── observation (page digest for the LLM, ≤ ~1.5k tokens) ──

    def digest(self, max_result_chars: int = 1200) -> str:
        return self.page.evaluate(_DIGEST_JS, max_result_chars)


# Structured text summary of the page (NOT raw DOM).  Passwords are masked.
_DIGEST_JS = r"""
(maxResult) => {
  const lines = [];
  const seen = new Set();
  let sidebar = document.querySelector('.st-dc-sidebar');
  if (!sidebar) {
    // Non-DC pages (e.g. /sqlreview): generic digest — visible labeled
    // inputs, dropdowns, buttons, and the report/result area.
    const parts = [];
    document.querySelectorAll('label').forEach(lb => {
      const span = lb.querySelector("span[data-testid='block-info'], span");
      const name = span ? span.textContent.trim() : '';
      const ta = lb.querySelector('textarea, input');
      if (!name || !ta || ta.type === 'checkbox') return;
      if (ta.offsetParent === null) return;
      const val = ta.type === 'password' ? '<masked>'
                  : (ta.value.length > 200 ? ta.value.slice(0, 200) + '…' : ta.value);
      parts.push(`${name}="${val}"`);
    });
    document.querySelectorAll("input[role='combobox']").forEach(inp => {
      if (inp.offsetParent === null) return;
      parts.push(`${inp.getAttribute('aria-label') || 'dropdown'}(dropdown)="${inp.value}"`);
    });
    if (parts.length) lines.push('[INPUTS] ' + parts.join(' | '));
    const btns = [];
    document.querySelectorAll('button').forEach(b => {
      if (b.offsetParent === null || b.classList.contains('label-wrap')) return;
      const t = b.textContent.trim().replace(/\s+/g, ' ');
      if (t && t.length < 40) btns.push(t);
    });
    lines.push('[BUTTONS] ' + btns.join(' | '));
    const reps = document.querySelectorAll('.sr-report-card, .prose');
    const rep = reps.length ? reps[reps.length - 1] : null;
    if (rep) {
      let txt = (rep.innerText || '').replace(/\n{2,}/g, '\n').trim();
      if (txt.length > maxResult) txt = txt.slice(0, maxResult) + ' …';
      lines.push('[RESULT] ' + txt);
    }
    return lines.join('\n');
  }

  // A/B panels = ancestor columns of the two status boxes
  const statuses = sidebar.querySelectorAll('.st-sidebar-status');
  const panels = [];
  statuses.forEach(st => {
    let el = st;
    while (el && !(el.classList && el.classList.contains('column'))) el = el.parentElement;
    if (el) panels.push(el);
  });
  const collectInputs = (root, parts) => {
    root.querySelectorAll('label').forEach(lb => {
      const span = lb.querySelector("span[data-testid='block-info'], span");
      const name = span ? span.textContent.trim() : '';
      if (!name) return;
      const ta = lb.querySelector('textarea, input');
      if (!ta || ta.type === 'checkbox') return;
      if (ta.offsetParent === null) return;   // hidden
      const val = ta.type === 'password' ? '<masked>' : ta.value;
      parts.push(`${name}="${val}"`);
      seen.add(lb);
    });
    // Gradio 6 dropdowns: no <label>, aria-label on the combobox input
    root.querySelectorAll("input[role='combobox']").forEach(inp => {
      if (inp.offsetParent === null) return;
      const name = inp.getAttribute('aria-label') || 'dropdown';
      parts.push(`${name}(dropdown)="${inp.value}"`);
      seen.add(inp);
    });
  };

  panels.forEach((panel, pi) => {
    const tag = pi === 0 ? 'PANEL A' : 'PANEL B';
    const parts = [];
    collectInputs(panel, parts);
    lines.push(`[${tag}] ` + parts.join(' | '));
  });

  // global sidebar inputs (not inside panels)
  const globalParts = [];
  sidebar.querySelectorAll('label').forEach(lb => {
    if (seen.has(lb)) return;
    if (panels.some(p => p.contains(lb))) return;
    const span = lb.querySelector("span[data-testid='block-info'], span");
    const name = span ? span.textContent.trim() : '';
    if (!name) return;
    const ta = lb.querySelector('textarea, input');
    if (!ta) return;
    if (ta.offsetParent === null) return;
    if (ta.type === 'checkbox') {
      globalParts.push(`${name}=[${ta.checked ? 'x' : ' '}]`);
    } else {
      const val = ta.type === 'password' ? '<masked>' : ta.value;
      globalParts.push(`${name}="${val}"`);
    }
  });
  sidebar.querySelectorAll("input[role='combobox']").forEach(inp => {
    if (seen.has(inp)) return;
    if (panels.some(p => p.contains(inp))) return;
    if (inp.offsetParent === null) return;
    const name = inp.getAttribute('aria-label') || 'dropdown';
    globalParts.push(`${name}(dropdown)="${inp.value}"`);
  });
  if (globalParts.length) lines.push('[INPUTS] ' + globalParts.join(' | '));

  // visible buttons
  const btns = [];
  sidebar.querySelectorAll('button').forEach(b => {
    if (b.offsetParent === null) return;
    const t = b.textContent.trim().replace(/\s+/g, ' ');
    if (t && t.length < 30 && !b.classList.contains('label-wrap')) btns.push(t);
  });
  lines.push('[BUTTONS] ' + btns.join(' | '));

  // accordions and open/closed state
  const accs = [];
  sidebar.querySelectorAll('.label-wrap').forEach(a => {
    const t = a.textContent.trim().replace(/\s+/g, ' ').replace(/[▼▲]/g, '').trim();
    const open = a.classList.contains('open');
    accs.push(`${t}(${open ? 'open' : 'closed'})`);
  });
  if (accs.length) lines.push('[ACCORDIONS] ' + accs.join(' | '));

  // result area: visible text, plus the content of collapsed <details>
  // previews (row data hides in there — the judge must see it)
  const res = document.querySelector('.st-main .st-schema-card');
  if (res) {
    let txt = res.innerText.replace(/\n{2,}/g, '\n').trim();
    res.querySelectorAll('details:not([open])').forEach(d => {
      const inner = (d.textContent || '').replace(/\s+/g, ' ').trim();
      if (inner) txt += '\n[折叠预览] ' + inner;
    });
    if (txt.length > maxResult) txt = txt.slice(0, maxResult) + ' …';
    lines.push(`[RESULT] ` + txt);
  }
  return lines.join('\n');
}
"""
