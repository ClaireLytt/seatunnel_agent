"""Settings page — configure the LLM API from the browser instead of .env."""

from __future__ import annotations

import os
import time

import gradio as gr

from . import settings_store

_I18N = {
    "en": {
        "title": "## ⚙️ Settings",
        "subtitle": "Configure the LLM API here — no need to edit the local `.env` file. "
                    "Saved values override `.env` for the web UI and take effect immediately. "
                    "Blank fields keep the current configuration shown below.",
        "provider": "Provider",
        "api_key": "API Key",
        "api_key_ph": "sk-... (leave blank to keep the current key)",
        "model": "Model Name",
        "model_ph": "e.g. claude-opus-5 / deepseek-chat",
        "base_url": "Base URL",
        "base_url_ph": "OpenAI-compatible endpoint, e.g. https://api.deepseek.com (blank for official)",
        "advanced": "Advanced",
        "temperature": "Temperature (0-2)",
        "max_tokens": "Max Tokens",
        "timeout": "Timeout (s)",
        "save": "Save",
        "test": "Test Connection",
        "reset": "Restore .env",
        "current": "Current configuration",
        "src_ui": "saved in Settings (overrides .env)",
        "src_env": ".env / environment",
        "not_set": "(not set)",
        "saved_ok": "✅ Saved — takes effect immediately",
        "saved_no_key": "⚠️ Saved, but no API Key is configured yet — chat pages will fail until one is set",
        "reset_ok": "✅ Restored — the web UI now follows .env again",
        "no_key": "No API Key — fill in the API Key field (or .env) first",
        "testing_sys": "You are a connectivity check. Reply with exactly: ok",
        "test_ok": "Connection OK",
        "test_fail": "Connection failed",
        "err_base_url": "Base URL must start with http:// or https://",
        "err_temp": "Temperature must be a number between 0 and 2",
        "err_max_tokens": "Max Tokens must be a positive integer",
        "err_timeout": "Timeout must be a positive integer (seconds)",
        "err_auth": "authentication failed — check the API Key",
        "err_notfound": "model or endpoint not found — check Model Name / Base URL",
        "err_conn": "cannot reach the endpoint — check Base URL / network",
        "profiles": "Profiles",
        "profiles_hint": "Save the current form as a named profile "
                         "(e.g. one per provider) and switch with one click.",
        "prof_name": "Profile Name",
        "prof_name_ph": "e.g. kimi / deepseek / claude",
        "prof_pick": "Profile",
        "prof_save": "Save as Profile",
        "prof_use": "Activate Profile",
        "prof_del": "Delete Profile",
        "prof_saved": "✅ Profile saved",
        "prof_used": "✅ Profile activated — takes effect immediately",
        "prof_deleted": "✅ Profile deleted",
        "prof_name_req": "❌ Profile name is required",
        "prof_pick_req": "❌ Pick a profile first",
        "usage": "LLM Usage (30 days)",
        "conns": "Database Connections",
        "conns_hint": "Shared with the Data Comparison page's connection "
                      "presets (passwords encrypted at rest under "
                      "`~/.seatunnel-agent/`).",
        "conn_name": "Name",
        "conn_type": "Type",
        "conn_env": "Environment",
        "conn_host": "Host",
        "conn_port": "Port",
        "conn_db": "Database",
        "conn_user": "Username",
        "conn_pwd": "Password",
        "conn_save": "Save Connection",
        "conn_del_pick": "Connection",
        "conn_del": "Delete Connection",
        "conn_saved": "✅ Connection saved",
        "conn_deleted": "✅ Connection deleted",
        "conn_name_req": "❌ Connection name is required",
        "conn_port_bad": "❌ Port must be an integer",
        "conn_pick_req": "❌ Pick a connection first",
    },
    "zh": {
        "title": "## ⚙️ 设置",
        "subtitle": "在这里配置 LLM API,无需修改本地 `.env` 文件。"
                    "保存后立即生效,并覆盖 `.env` 中的同名配置(仅影响 Web 界面)。"
                    "留空的字段保持下方当前配置不变。",
        "provider": "提供商",
        "api_key": "API Key",
        "api_key_ph": "sk-...(留空则保持当前已保存的 Key)",
        "model": "模型名称",
        "model_ph": "如 claude-opus-5 / deepseek-chat",
        "base_url": "Base URL",
        "base_url_ph": "OpenAI 兼容端点,如 https://api.deepseek.com(留空用官方地址)",
        "advanced": "高级设置",
        "temperature": "温度 (0-2)",
        "max_tokens": "最大 Token 数",
        "timeout": "超时(秒)",
        "save": "保存",
        "test": "测试连接",
        "reset": "恢复 .env",
        "current": "当前生效配置",
        "src_ui": "界面设置(覆盖 .env)",
        "src_env": ".env / 环境变量",
        "not_set": "(未设置)",
        "saved_ok": "✅ 已保存,立即生效",
        "saved_no_key": "⚠️ 已保存,但尚未配置 API Key,聊天类页面暂不可用",
        "reset_ok": "✅ 已恢复,Web 界面重新使用 .env 配置",
        "no_key": "缺少 API Key,请先填写 API Key(或配置 .env)",
        "testing_sys": "You are a connectivity check. Reply with exactly: ok",
        "test_ok": "连接成功",
        "test_fail": "连接失败",
        "err_base_url": "Base URL 必须以 http:// 或 https:// 开头",
        "err_temp": "温度必须是 0 到 2 之间的数字",
        "err_max_tokens": "最大 Token 数必须是正整数",
        "err_timeout": "超时必须是正整数(秒)",
        "err_auth": "鉴权失败,请检查 API Key",
        "err_notfound": "模型或端点不存在,请检查模型名称 / Base URL",
        "err_conn": "无法连接端点,请检查 Base URL / 网络",
        "profiles": "配置档案",
        "profiles_hint": "把当前表单存为命名档案(如每个提供商一套),一键切换。",
        "prof_name": "档案名",
        "prof_name_ph": "如 kimi / deepseek / claude",
        "prof_pick": "选择档案",
        "prof_save": "存为档案",
        "prof_use": "启用档案",
        "prof_del": "删除档案",
        "prof_saved": "✅ 已存为档案",
        "prof_used": "✅ 已启用档案,立即生效",
        "prof_deleted": "✅ 已删除档案",
        "prof_name_req": "❌ 请填写档案名",
        "prof_pick_req": "❌ 请先选择档案",
        "usage": "LLM 用量(近 30 天)",
        "conns": "数据库连接",
        "conns_hint": "与数据对比页的连接预设共用一份存储(密码加密保存在 "
                      "`~/.seatunnel-agent/` 下)。",
        "conn_name": "名称",
        "conn_type": "类型",
        "conn_env": "环境",
        "conn_host": "主机",
        "conn_port": "端口",
        "conn_db": "数据库",
        "conn_user": "用户名",
        "conn_pwd": "密码",
        "conn_save": "保存连接",
        "conn_del_pick": "选择连接",
        "conn_del": "删除连接",
        "conn_saved": "✅ 已保存连接",
        "conn_deleted": "✅ 已删除连接",
        "conn_name_req": "❌ 请填写连接名称",
        "conn_port_bad": "❌ 端口必须是整数",
        "conn_pick_req": "❌ 请先选择连接",
    },
}


def _t(lang: str, key: str) -> str:
    return _I18N.get(lang, _I18N["en"]).get(key, key)


def _effective_key() -> str:
    return os.getenv("API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", "")


def _ds_choices() -> list[str]:
    from .text2sql.executor import DIALECT_NAMES, DS_TYPES
    return [DIALECT_NAMES[d] for d in DS_TYPES]


def _presets_store():
    from .data_comparison.presets import ConnectionPresetsStore
    return ConnectionPresetsStore()


def _conn_names() -> list[str]:
    try:
        return [p.get("name", "") for p in _presets_store().list()]
    except Exception:  # noqa: BLE001 — never break the page over the store
        return []


def _conn_summary(lang: str) -> str:
    """Markdown table of saved connections; passwords never shown."""
    zh = lang == "zh"
    try:
        presets = _presets_store().list()
    except Exception:  # noqa: BLE001
        presets = []
    if not presets:
        return "暂无已保存的连接" if zh else "No saved connections"
    rows = ["| " + ("名称 | 类型 | 地址 | 数据库 | 用户" if zh
                    else "Name | Type | Address | Database | User") + " |",
            "|---|---|---|---|---|"]
    for p in presets:
        rows.append(
            f"| **{p.get('name', '')}** | {p.get('ds_type', '')} "
            f"| `{p.get('host', '')}:{p.get('port', '')}` "
            f"| {p.get('database', '')} | {p.get('username', '') or '—'} |")
    return "\n".join(rows)


def _usage_markdown(lang: str) -> str:
    from .llm_usage import format_markdown
    try:
        return format_markdown(lang)
    except Exception:  # noqa: BLE001 — stats must never break the page
        return ""


def _current_summary(lang: str) -> str:
    """Markdown block showing the effective LLM config and where it came from."""
    t = lambda k: _t(lang, k)
    src = t("src_ui") if settings_store.has_saved() else t("src_env")
    key = settings_store.mask_secret(_effective_key()) or t("not_set")
    base = os.getenv("LLM_BASE_URL", "") or t("not_set")
    return (
        f"**{t('current')}** · {src}\n\n"
        f"- {t('provider')}: `{os.getenv('LLM_PROVIDER', 'anthropic')}`"
        f" · {t('model')}: `{os.getenv('MODEL_NAME', 'claude-opus-5')}`\n"
        f"- {t('api_key')}: `{key}` · {t('base_url')}: `{base}`"
    )


def _validate(base_url: str, temp: str, max_tokens: str, timeout: str,
              lang: str) -> str | None:
    """Return a localized error message, or None when all inputs are valid."""
    base_url = (base_url or "").strip()
    if base_url and not base_url.startswith(("http://", "https://")):
        return _t(lang, "err_base_url")
    temp = (temp or "").strip()
    if temp:
        try:
            v = float(temp)
        except ValueError:
            return _t(lang, "err_temp")
        if not 0 <= v <= 2:
            return _t(lang, "err_temp")
    for raw, err in ((max_tokens, "err_max_tokens"), (timeout, "err_timeout")):
        raw = (raw or "").strip()
        if raw:
            try:
                if int(raw) <= 0:
                    return _t(lang, err)
            except ValueError:
                return _t(lang, err)
    return None


def _map_error(exc: Exception, key: str, lang: str) -> str:
    """One-line, localized, key-redacted reason for a failed connection test."""
    name = type(exc).__name__
    msg = str(exc)
    if key:
        msg = msg.replace(key, "***")
    low = f"{name} {msg}".lower()
    if "authentication" in low or "401" in low or "invalid api key" in low \
            or "invalid x-api-key" in low:
        return _t(lang, "err_auth")
    if "notfound" in low or "404" in low or "does not exist" in low:
        return _t(lang, "err_notfound")
    if "connection" in low or "timeout" in low or "timed out" in low \
            or "unreachable" in low or "getaddrinfo" in low:
        return _t(lang, "err_conn")
    return f"{name}: {msg[:200]}"


def render_settings_page(app: gr.Blocks) -> None:
    from dotenv import load_dotenv
    load_dotenv()
    settings_store.apply_to_env()

    lang_state = gr.State("en")
    t = lambda k: _t("en", k)

    with gr.Column(elem_classes=["st-set-page"]):
        with gr.Row():
            title_md = gr.Markdown(t("title"))
            home_btn = gr.Button("\U0001f3e0", size="sm", scale=0,
                                 elem_classes=["st-home-btn"])
        # st-set-main breaks the fixed-height flex chain (same trick as
        # .st-lin-main etc.): children grow naturally, the page scrolls.
        with gr.Column(elem_classes=["st-set-main"]):
            subtitle_md = gr.Markdown(t("subtitle"))
            current_md = gr.Markdown(_current_summary("en"))

            # The form starts EMPTY on purpose: the current config is shown
            # (masked) in the summary above, and only filled-in fields
            # override it on save — blank fields keep what's already there.
            provider_dd = gr.Dropdown(
                label=t("provider"), choices=["", "anthropic", "openai"],
                value="",
            )
            api_key_tb = gr.Textbox(
                label=t("api_key"), type="password", placeholder=t("api_key_ph"),
            )
            model_tb = gr.Textbox(
                label=t("model"), placeholder=t("model_ph"),
            )
            base_url_tb = gr.Textbox(
                label=t("base_url"), placeholder=t("base_url_ph"),
            )
            with gr.Accordion(t("advanced"), open=False) as adv_acc:
                temp_tb = gr.Textbox(label=t("temperature"))
                max_tokens_tb = gr.Textbox(label=t("max_tokens"))
                timeout_tb = gr.Textbox(label=t("timeout"))
            with gr.Row():
                save_btn = gr.Button(t("save"), variant="primary")
                test_btn = gr.Button(t("test"))
                reset_btn = gr.Button(t("reset"))
            with gr.Accordion(t("profiles"), open=False) as prof_acc:
                gr.Markdown(t("profiles_hint"))
                with gr.Row():
                    prof_name_tb = gr.Textbox(
                        label=t("prof_name"), placeholder=t("prof_name_ph"))
                    prof_dd = gr.Dropdown(
                        label=t("prof_pick"),
                        choices=settings_store.list_profiles())
                with gr.Row():
                    save_prof_btn = gr.Button(t("prof_save"), size="sm")
                    use_prof_btn = gr.Button(t("prof_use"), size="sm",
                                             variant="primary")
                    del_prof_btn = gr.Button(t("prof_del"), size="sm")
            with gr.Accordion(t("conns"), open=False) as conn_acc:
                gr.Markdown(t("conns_hint"))
                conn_list_md = gr.Markdown(_conn_summary("en"))
                with gr.Row():
                    conn_name_tb = gr.Textbox(label=t("conn_name"), scale=2)
                    conn_type_dd = gr.Dropdown(
                        label=t("conn_type"), choices=_ds_choices(), scale=2)
                    conn_env_tb = gr.Textbox(label=t("conn_env"), scale=1)
                with gr.Row():
                    conn_host_tb = gr.Textbox(label=t("conn_host"), scale=2)
                    conn_port_tb = gr.Textbox(label=t("conn_port"), scale=1)
                    conn_db_tb = gr.Textbox(label=t("conn_db"), scale=2)
                with gr.Row():
                    conn_user_tb = gr.Textbox(label=t("conn_user"))
                    conn_pwd_tb = gr.Textbox(label=t("conn_pwd"),
                                             type="password")
                with gr.Row():
                    conn_save_btn = gr.Button(t("conn_save"), size="sm",
                                              variant="primary")
                    conn_del_dd = gr.Dropdown(label=t("conn_del_pick"),
                                              choices=_conn_names(), scale=2)
                    conn_del_btn = gr.Button(t("conn_del"), size="sm")
            with gr.Accordion(t("usage"), open=False) as usage_acc:
                usage_md = gr.Markdown("")
            status_md = gr.Markdown("")

    # ── Callbacks ──

    def _do_save(provider, api_key, model, base_url, temp, max_toks, timeout, lang):
        err = _validate(base_url, temp, max_toks, timeout, lang)
        if err:
            return f"❌ {err}", gr.update(), gr.update()
        # Blank fields keep the existing saved override — only what you fill
        # in changes; "Restore .env" is the way to drop overrides entirely.
        merged = settings_store.load_saved()
        for key, val in (
            ("LLM_PROVIDER", provider),
            ("API_KEY", api_key),
            ("MODEL_NAME", model),
            ("LLM_BASE_URL", base_url),
            ("TEMPERATURE", temp),
            ("MAX_TOKENS", max_toks),
            ("LLM_TIMEOUT", timeout),
        ):
            val = (val or "").strip()
            if val:
                merged[key] = val
        settings_store.save(merged)
        msg = _t(lang, "saved_ok") if _effective_key() else _t(lang, "saved_no_key")
        return msg, _current_summary(lang), gr.update(value="")

    def _do_test(provider, api_key, model, base_url, temp, max_toks, timeout, lang):
        err = _validate(base_url, temp, max_toks, timeout, lang)
        if err:
            return f"❌ {err}"
        # Blank fields test the currently effective config (env already
        # reflects saved overrides after apply_to_env).
        key = (api_key or "").strip() \
            or settings_store.load_saved().get("API_KEY", "") or _effective_key()
        if not key:
            return f"❌ {_t(lang, 'no_key')}"
        from .config import Settings
        from .llm import LLMClient
        try:
            timeout_s = min(int((timeout or "").strip()
                                or os.getenv("LLM_TIMEOUT", "") or 10), 30)
        except ValueError:
            timeout_s = 10
        s = Settings(
            api_key=key,
            llm_provider=(provider or "").strip()
            or os.getenv("LLM_PROVIDER", "anthropic"),
            model_name=(model or "").strip() or os.getenv("MODEL_NAME", "claude-opus-5"),
            llm_base_url=(base_url or "").strip() or os.getenv("LLM_BASE_URL", ""),
            max_tokens=64,
            temperature=0.0,
            llm_timeout=timeout_s,
        )
        t0 = time.time()
        try:
            resp = LLMClient(s).chat(
                _t(lang, "testing_sys"), [{"role": "user", "content": "ping"}])
            ms = int((time.time() - t0) * 1000)
            reply = (resp.reply_text or "").strip().replace("\n", " ")[:60]
            return f"✅ {_t(lang, 'test_ok')} · `{s.model_name}` · {ms}ms · {reply}"
        except Exception as e:  # noqa: BLE001 — every failure maps to a reason
            return f"❌ {_t(lang, 'test_fail')}: {_map_error(e, key, lang)}"

    def _do_reset(lang):
        settings_store.clear()
        return f"{_t(lang, 'reset_ok')}", _current_summary(lang)

    def _merged_form(provider, api_key, model, base_url, temp, max_toks, timeout):
        """Active overrides overlaid with the non-blank form fields."""
        merged = settings_store.load_saved()
        for key, val in (
            ("LLM_PROVIDER", provider), ("API_KEY", api_key),
            ("MODEL_NAME", model), ("LLM_BASE_URL", base_url),
            ("TEMPERATURE", temp), ("MAX_TOKENS", max_toks),
            ("LLM_TIMEOUT", timeout),
        ):
            val = (val or "").strip()
            if val:
                merged[key] = val
        return merged

    def _save_profile(name, provider, api_key, model, base_url, temp,
                      max_toks, timeout, lang):
        if not (name or "").strip():
            return _t(lang, "prof_name_req"), gr.update()
        err = _validate(base_url, temp, max_toks, timeout, lang)
        if err:
            return f"❌ {err}", gr.update()
        try:
            settings_store.save_profile(
                name, _merged_form(provider, api_key, model, base_url,
                                   temp, max_toks, timeout))
        except ValueError as e:
            return f"❌ {e}", gr.update()
        return (f"{_t(lang, 'prof_saved')}: {name.strip()}",
                gr.update(choices=settings_store.list_profiles(),
                          value=name.strip()))

    def _use_profile(name, lang):
        if not name:
            return _t(lang, "prof_pick_req"), gr.update()
        try:
            settings_store.activate_profile(name)
        except KeyError:
            return _t(lang, "prof_pick_req"), gr.update()
        return (f"{_t(lang, 'prof_used')}: {name}", _current_summary(lang))

    def _del_profile(name, lang):
        if not name:
            return _t(lang, "prof_pick_req"), gr.update()
        settings_store.delete_profile(name)
        return (f"{_t(lang, 'prof_deleted')}: {name}",
                gr.update(choices=settings_store.list_profiles(), value=None))

    def _save_conn(name, ds_type, env, host, port, db, user, pwd, lang):
        if not (name or "").strip():
            return _t(lang, "conn_name_req"), gr.update(), gr.update()
        port_s = (port or "").strip()
        try:
            port_i = int(port_s) if port_s else 0
        except ValueError:
            return _t(lang, "conn_port_bad"), gr.update(), gr.update()
        _presets_store().save(
            name=name, ds_type=ds_type or "", host=(host or "").strip(),
            port=port_i, database=(db or "").strip(),
            username=(user or "").strip(), password=pwd or "",
            environment=(env or "").strip())
        return (f"{_t(lang, 'conn_saved')}: {name.strip()}",
                _conn_summary(lang),
                gr.update(choices=_conn_names(), value=name.strip()))

    def _del_conn(name, lang):
        if not name:
            return _t(lang, "conn_pick_req"), gr.update(), gr.update()
        store = _presets_store()
        preset = store.get_by_name(name)
        if preset:
            store.delete(preset["id"])
        return (f"{_t(lang, 'conn_deleted')}: {name}", _conn_summary(lang),
                gr.update(choices=_conn_names(), value=None))

    def _switch_lang(sel):
        lang = "zh" if sel == "中文" else "en"
        t = lambda k: _t(lang, k)
        return (
            lang,
            gr.update(value=t("title")),
            gr.update(value=t("subtitle")),
            gr.update(value=_current_summary(lang)),
            gr.update(label=t("provider")),
            gr.update(label=t("api_key"), placeholder=t("api_key_ph")),
            gr.update(label=t("model"), placeholder=t("model_ph")),
            gr.update(label=t("base_url"), placeholder=t("base_url_ph")),
            gr.update(label=t("advanced")),
            gr.update(label=t("temperature")),
            gr.update(label=t("max_tokens")),
            gr.update(label=t("timeout")),
            gr.update(value=t("save")),
            gr.update(value=t("test")),
            gr.update(value=t("reset")),
            gr.update(label=t("profiles")),
            gr.update(label=t("prof_name"), placeholder=t("prof_name_ph")),
            # choices are baked at build time — refresh them here so a fresh
            # page load sees profiles saved in other sessions/page loads
            gr.update(label=t("prof_pick"),
                      choices=settings_store.list_profiles()),
            gr.update(value=t("prof_save")),
            gr.update(value=t("prof_use")),
            gr.update(value=t("prof_del")),
            gr.update(label=t("usage")),
            gr.update(value=_usage_markdown(lang)),
            gr.update(label=t("conns")),
            gr.update(value=_conn_summary(lang)),
            gr.update(label=t("conn_name")),
            gr.update(label=t("conn_type")),
            gr.update(label=t("conn_env")),
            gr.update(label=t("conn_host")),
            gr.update(label=t("conn_port")),
            gr.update(label=t("conn_db")),
            gr.update(label=t("conn_user")),
            gr.update(label=t("conn_pwd")),
            gr.update(value=t("conn_save")),
            gr.update(label=t("conn_del_pick"), choices=_conn_names()),
            gr.update(value=t("conn_del")),
        )

    form_inputs = [provider_dd, api_key_tb, model_tb, base_url_tb,
                   temp_tb, max_tokens_tb, timeout_tb, lang_state]
    save_btn.click(_do_save, inputs=form_inputs,
                   outputs=[status_md, current_md, api_key_tb])
    test_btn.click(_do_test, inputs=form_inputs, outputs=[status_md])
    reset_btn.click(_do_reset, inputs=[lang_state],
                    outputs=[status_md, current_md])
    save_prof_btn.click(_save_profile,
                        inputs=[prof_name_tb, *form_inputs],
                        outputs=[status_md, prof_dd])
    use_prof_btn.click(_use_profile, inputs=[prof_dd, lang_state],
                       outputs=[status_md, current_md])
    del_prof_btn.click(_del_profile, inputs=[prof_dd, lang_state],
                       outputs=[status_md, prof_dd])
    conn_save_btn.click(
        _save_conn,
        inputs=[conn_name_tb, conn_type_dd, conn_env_tb, conn_host_tb,
                conn_port_tb, conn_db_tb, conn_user_tb, conn_pwd_tb,
                lang_state],
        outputs=[status_md, conn_list_md, conn_del_dd])
    conn_del_btn.click(_del_conn, inputs=[conn_del_dd, lang_state],
                       outputs=[status_md, conn_list_md, conn_del_dd])
    from .lang_pref import HOME_JS, STAMP_JS, choice_from_request
    home_btn.click(fn=None, js=HOME_JS)
    # Language follows the hub's choice (st-lang cookie), applied on load.
    app.load(fn=None, js=STAMP_JS)

    def _lang_on_load(request: gr.Request):
        return _switch_lang(choice_from_request(request))

    app.load(
        _lang_on_load, inputs=None,
        outputs=[lang_state, title_md, subtitle_md, current_md, provider_dd,
                 api_key_tb, model_tb, base_url_tb, adv_acc, temp_tb,
                 max_tokens_tb, timeout_tb, save_btn, test_btn, reset_btn,
                 prof_acc, prof_name_tb, prof_dd, save_prof_btn,
                 use_prof_btn, del_prof_btn, usage_acc, usage_md,
                 conn_acc, conn_list_md, conn_name_tb, conn_type_dd,
                 conn_env_tb, conn_host_tb, conn_port_tb, conn_db_tb,
                 conn_user_tb, conn_pwd_tb, conn_save_btn, conn_del_dd,
                 conn_del_btn],
    )
