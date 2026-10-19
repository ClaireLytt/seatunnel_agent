"""i18n parity for the React /dataskew workspace (ticket 04).

Checks frontend/data_skew/src/i18n.ts (modeled on
tests/test_transpile_i18n.py):

- en and zh expose identical key sets;
- every t('key') used in the workspace .tsx files is defined;
- keys ported from the backend dsk() dict carry its wording verbatim
  (expected values pinned against the LIVE backend dict — unlike earlier
  migrations the source dict survives in agents/data/data_skew/i18n.py,
  so parity is asserted against it directly instead of inline copies).

Keys with no backend counterpart to check (new UI text on the React page):
- title: the backend `dsk_title` is a markdown blob "## ⚖️ SQL Data Skew
  Analyzer"; React drops the "## " and moves the ⚖️ glyph next to the h1.
- home/copy/copied: hub nav + SqlView copy button (shell/gr.Code had
  built-ins).
- Guard/validation and report wording stays backend-rendered (structured
  {code, message} errors / report markdown) and is deliberately NOT in
  i18n.ts.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "frontend" / "data_skew" / "src"
I18N_TS = SRC / "i18n.ts"

# React key -> backend dsk() key whose en/zh wording it must carry
# verbatim ({var} placeholders become i18next {{var}}).
BACKEND_PINNED: dict[str, str] = {
    "subtitle": "dsk_subtitle",
    "sql_ph": "dsk_sql_placeholder",
    "dialect": "dsk_dialect",
    "mode": "dsk_mode",
    "mode_static": "dsk_mode_static",
    "mode_llm": "dsk_mode_llm",
    "analyze_btn": "dsk_analyze_btn",
    "upload_btn": "dsk_upload_btn",
    "clear_btn": "dsk_clear_btn",
    "running_static": "dsk_running_static",
    "running_llm": "dsk_running_llm",
    "download_report": "dsk_download_report",
    "download_sql": "dsk_download_sql",
    "optimized_sql": "dsk_optimized_sql",
    "history_accordion": "dsk_history_accordion",
    "history_refresh": "dsk_history_refresh",
    "history_load": "dsk_history_load",
    "history_pick": "dsk_history_pick",
    "h_time": "dsk_h_time",
    "h_source": "dsk_h_source",
    "h_dialect": "dsk_h_dialect",
    "h_mode": "dsk_h_mode",
    "h_findings": "dsk_h_findings",
    "h_sql": "dsk_h_sql",
    "conn_accordion": "dsk_conn_accordion",
    "preset_dd": "dsk_preset_dd",
    "preset_load": "dsk_preset_load",
    "preset_none": "dsk_preset_none",
    "preset_unsupported": "dsk_preset_unsupported",
    "ds_type": "dsk_ds_type",
    "sample": "dsk_sample",
    "sample_full": "dsk_sample_full",
    "host": "dsk_host",
    "port": "dsk_port",
    "db": "dsk_db",
    "user": "dsk_user",
    "pwd": "dsk_pwd",
    "connect_btn": "dsk_connect_btn",
    "verify_btn": "dsk_verify_btn",
    "cst_btn": "cst_btn",
    "conn_status_none": "dsk_conn_status_none",
    "conn_handoff": "dsk_conn_handoff",
    "conn_handoff_unsupported": "dsk_conn_handoff_unsupported",
    "verify_running": "dsk_verify_running",
    "cst_running": "cst_running",
    "spk_accordion": "spk_accordion",
    "spk_conf_ph": "spk_conf_placeholder",
    "spk_btn": "spk_btn",
    "spk_apply_dl": "spk_apply_dl",
    "rt_accordion": "rt_accordion",
    "rt_url": "rt_url",
    "rt_app": "rt_app",
    "rt_btn": "rt_btn",
    "rt_upload_btn": "rt_upload_btn",
    "rt_running": "rt_running",
}

# Markdown-italic placeholders/empties where React drops the * wrappers.
STRIP_STARS = {"history_empty": "dsk_history_empty",
               "report_placeholder": "dsk_report_placeholder"}


def _parse_locale(block: str) -> dict[str, str]:
    # keys may be multi-part string concatenations ('a ' + 'b'); join them
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


def _backend() -> dict[str, dict[str, str]]:
    import seatunnel_agent.agents.data.data_skew.i18n as mod

    return next(v for n in dir(mod) for v in [getattr(mod, n)]
                if isinstance(v, dict) and "en" in v and "zh" in v)


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


def test_pinned_keys_match_backend_verbatim() -> None:
    res = _resources()
    backend = _backend()
    problems: list[str] = []
    for react_key, dsk_key in BACKEND_PINNED.items():
        for lang in ("en", "zh"):
            expected = backend[lang][dsk_key].replace("{", "{{").replace(
                "}", "}}") if "{" in backend[lang][dsk_key] else backend[lang][dsk_key]
            got = res[lang].get(react_key)
            if got != expected:
                problems.append(
                    f"{lang}.{react_key}: {got!r} != backend {dsk_key} {expected!r}")
    assert not problems, "\n".join(problems)


def test_stripped_star_keys_match_backend() -> None:
    res = _resources()
    backend = _backend()
    for react_key, dsk_key in STRIP_STARS.items():
        for lang in ("en", "zh"):
            assert res[lang][react_key] == backend[lang][dsk_key].strip("*")


def test_i18n_initialized_from_lang_cookie() -> None:
    text = I18N_TS.read_text(encoding="utf-8")
    assert "langFromCookie" in text
    assert re.search(r"lng:\s*langFromCookie\(\)", text)
