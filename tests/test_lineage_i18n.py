"""i18n parity for the React /lineage workspace (ticket 04).

Checks frontend/data_lineage/src/i18n.ts (modeled on
tests/test_dataskew_i18n.py):

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the legacy Gradio page carry the _I18N wording
  verbatim (expected values live INLINE below, copied from the retired
  agents/data/data_lineage/ui.py at 6c108e1^; {var} placeholders become
  i18next {{var}}).

Keys with documented deviations (noted in i18n.ts):
- title/subtitle: the legacy markdown blob is split, "## " and the 🩸
  glyph move to the h1; section headings drop the "### ".
- not_loaded/report_ph: markdown *italics* wrappers dropped.
- home/copy/copied/no_settings: hub nav, copy button, SSE no-key message
  (legacy showed backend-raised text; React localizes the structured
  no_settings frame).
- Keys that stayed backend-side (built_stats/not_found/similar/fail/
  snap_not_found…) are rendered by the backend or rebuilt in App.tsx's
  statsLine — not required in i18n.ts.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "data_lineage" / "src"
I18N_TS = SRC / "i18n.ts"

# React key -> {en, zh} legacy wording, verbatim from _I18N
# (retired src/.../data_lineage/ui.py, git 6c108e1^).
LEGACY_EXPECTED: dict[str, dict[str, str]] = {
    "sql_dir_label": {"en": "SQL directory", "zh": "SQL 目录"},
    "sql_dir_ph": {"en": "Directory containing *.sql files (scanned recursively)",
                   "zh": "包含 *.sql 文件的目录（递归扫描）"},
    "sql_dialect_label": {"en": "SQL dialect", "zh": "SQL 方言"},
    "st_dir_label": {"en": "SeaTunnel config directory", "zh": "SeaTunnel 配置目录"},
    "use_hive": {"en": "Load from the Hive metadata lineage table (requires HIVE_HOST in .env)",
                 "zh": "从 Hive 元数据血缘表加载（需 .env 配置 HIVE_HOST）"},
    "hive_adv": {"en": "Hive advanced options", "zh": "Hive 高级选项"},
    "meta_table_label": {"en": "Lineage metadata table", "zh": "血缘元数据表"},
    "partition_label": {"en": "pt partition", "zh": "pt 分区"},
    "load_btn": {"en": "Build lineage graph", "zh": "构建血缘图"},
    "table_label": {"en": "Target table", "zh": "目标表"},
    "direction_label": {"en": "Direction", "zh": "方向"},
    "dir_both": {"en": "Full chain (upstream + downstream)", "zh": "全链路（上游 + 下游）"},
    "dir_up": {"en": "Upstream only", "zh": "仅上游"},
    "dir_down": {"en": "Downstream only", "zh": "仅下游"},
    "depth_label": {"en": "Depth", "zh": "深度"},
    "column_label": {"en": "Column (optional)", "zh": "字段（可选）"},
    "column_ph": {"en": "Column-level impact analysis when set", "zh": "填写后做字段级影响分析"},
    "query_btn": {"en": "Query lineage", "zh": "查询血缘"},
    "search_label": {"en": "Table search", "zh": "表名搜索"},
    "search_ph": {"en": "Fuzzy search over loaded tables", "zh": "关键字模糊搜索已加载的表"},
    "search_btn": {"en": "Search", "zh": "搜索"},
    "path_dst_label": {"en": "Path destination table", "zh": "路径终点表"},
    "path_btn": {"en": "Find path", "zh": "查询路径"},
    "sla_delay_label": {"en": "Assumed delay (hours)", "zh": "假设延迟（小时）"},
    "sla_btn": {"en": "SLA impact analysis", "zh": "SLA 影响分析"},
    "health_btn": {"en": "Governance health check", "zh": "治理体检"},
    "mermaid_acc": {"en": "Mermaid source (copyable)", "zh": "Mermaid 源码（可复制）"},
    "agent_acc": {"en": "🤖 Agent Q&A (natural language, API key required)",
                  "zh": "🤖 Agent 问答（自然语言，需 API key）"},
    "ask_label": {"en": "Question", "zh": "问题"},
    "ask_btn": {"en": "Ask", "zh": "提问"},
    "need_source": {"en": "Provide a SQL directory or enable the Hive metadata option.",
                    "zh": "请至少提供 SQL 目录或勾选 Hive 元数据。"},
    "need_graph": {"en": "Build the lineage graph first.", "zh": "请先构建血缘图。"},
    "need_table": {"en": "Enter a target table.", "zh": "请输入目标表。"},
    "need_path_dst": {"en": "Enter the path destination table.", "zh": "请输入路径终点表。"},
    "need_keyword": {"en": "Enter a search keyword.", "zh": "请输入搜索关键字。"},
    "need_question": {"en": "Enter a question.", "zh": "请输入问题。"},
    "agent_running": {"en": "⏳ Analyzing…", "zh": "⏳ 分析中…"},
    "snap_name_label": {"en": "Snapshot name (optional)", "zh": "快照名（可选）"},
    "save_snap_btn": {"en": "Save snapshot", "zh": "保存快照"},
    "snap_dd_label": {"en": "Compare against snapshot", "zh": "对比快照"},
    "diff_snap_btn": {"en": "Compare snapshots", "zh": "快照对比"},
    "snap_saved": {"en": "✅ Snapshot saved: `{{file}}`", "zh": "✅ 快照已保存：`{{file}}`"},
    "need_snap": {"en": "Pick a snapshot to compare against.", "zh": "请选择要对比的快照。"},
}


def _parse_locale(block: str) -> dict[str, str]:
    pairs = re.findall(
        r"(\w+):\s*((?:'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|\s|\+)+)",
        block,
    )
    out: dict[str, str] = {}
    for key, raw in pairs:
        chunks = re.findall(r"'((?:[^'\\]|\\.)*)'|\"((?:[^\"\\]|\\.)*)\"", raw)
        val = "".join(a if a else b for a, b in chunks)
        out[key] = (val.replace("\\'", "'").replace('\\"', '"')
                    .replace("\\n", "\n"))
    return out


def _resources() -> dict[str, dict[str, str]]:
    text = I18N_TS.read_text(encoding="utf-8")
    locales = re.findall(
        r"^  (en|zh): \{\s*translation: \{(.*?)^    \},\s*^  \},",
        text,
        re.S | re.M,
    )
    assert {name for name, _ in locales} == {"en", "zh"}, "en/zh blocks not found"
    return {name: _parse_locale(body) for name, body in locales}


def _workspace_sources() -> list[str]:
    files = list(SRC.glob("*.tsx")) + list((SRC / "components").glob("*.tsx"))
    assert files, "no .tsx files found — glob broken?"
    return [f.read_text(encoding="utf-8") for f in files]


def test_en_zh_key_sets_match() -> None:
    res = _resources()
    assert res["en"], "no keys parsed from i18n.ts"
    assert set(res["en"]) == set(res["zh"])


def test_every_t_usage_is_defined() -> None:
    keys = set(_resources()["en"])
    used: set[str] = set()
    for text in _workspace_sources():
        used |= set(re.findall(r"\bt\('(\w+)'", text))
    assert used, "no t() usages found — glob broken?"
    missing = used - keys
    assert not missing, f"t() keys missing from i18n.ts: {sorted(missing)}"


def test_ported_keys_match_legacy_verbatim() -> None:
    res = _resources()
    problems: list[str] = []
    for react_key, expected_by_lang in LEGACY_EXPECTED.items():
        for lang in ("en", "zh"):
            got = res[lang].get(react_key)
            if got != expected_by_lang[lang]:
                problems.append(
                    f"{lang}.{react_key}: {got!r} != legacy {expected_by_lang[lang]!r}")
    assert not problems, "\n".join(problems)


def test_built_stats_line_matches_legacy() -> None:
    # built_stats lives in i18n.ts with {{var}} interpolation — pin both
    res = _resources()
    assert res["zh"]["built_stats"] == (
        "✅ 血缘图已构建：**{{tables}}** 表 · **{{edges}}** 边 · "
        "**{{col_edges}}** 字段边 · SLA 表 {{sla}} 张")
    assert res["en"]["built_stats"] == (
        "✅ Lineage graph built: **{{tables}}** tables · **{{edges}}** edges · "
        "**{{col_edges}}** column edges · {{sla}} SLA tables")


def test_i18n_initialized_via_shared_initI18n() -> None:
    # cookie-driven lng lives behind the shared seam now; the leaf only
    # declares resources (shared/src/i18n.ts carries langFromCookie)
    text = I18N_TS.read_text(encoding="utf-8")
    assert "initI18n(resources)" in text or "initI18n(" in text
    shared = (ROOT / "frontend" / "shared" / "src" / "i18n.ts").read_text(
        encoding="utf-8")
    assert re.search(r"lng:\s*langFromCookie\(\)", shared)
