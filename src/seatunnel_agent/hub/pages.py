"""Hub pages: landing (`/`), Data Agents (`/data`), AI Platform (`/ai`),
DevOps (`/devops`) — HTML builders and the shared mount helper."""

from __future__ import annotations

import html as _html
import os
import re

import gradio as gr

_DOCS_URL = "https://github.com/ClaireLytt/seatunnel_agent#readme"


def _hub_health_html() -> str:
    """Health strip under the hub subtitle — recomputed on every page load.

    Language-swapped by the same data-en/zh mechanism as the rest of the hub."""
    from seatunnel_agent.common import settings_store
    from seatunnel_agent.common.config import env_api_key
    key = env_api_key()
    if key:
        model = _html.escape(os.getenv("MODEL_NAME", "claude-opus-5"))
        src = "UI settings" if settings_store.has_saved() else ".env"
        llm = (f'<span class="st-hub-ok" title="configured via {src}">'
               f'<span class="st-dot st-dot-ok"></span>LLM'
               f'<code>{model}</code></span>')
    else:
        llm = ('<a href="/settings" class="st-hub-bad">'
               '<span class="st-dot st-dot-bad"></span>LLM '
               '<span data-en="not configured — open Settings" '
               'data-zh="未配置,点此设置">not configured — open Settings</span></a>')
    hive_host = os.getenv("HIVE_HOST", "")
    hive = (f'<span class="st-hub-ok" title="{_html.escape(hive_host)}">'
            '<span class="st-dot st-dot-ok"></span>Hive: '
            '<span data-en="connected" data-zh="已连接">connected</span></span>'
            if hive_host else
            '<span class="st-hub-dim"><span class="st-dot st-dot-off"></span>'
            'Hive: <span data-en="not set" data-zh="未配置">not set</span></span>')
    # agent count beats a developer-facing test tally on a landing page
    try:
        n = _agent_count()
        agents = (f'<span class="st-hub-ok"><span class="st-dot st-dot-ok">'
                  f'</span>{n} <span data-en="agents ready" '
                  f'data-zh="个能力就绪">agents ready</span></span>')
    except Exception:
        agents = ""
    import datetime as _dt
    today = _dt.date.today().strftime("%A, %B %d, %Y").upper()
    date_seg = f'<span class="st-hub-dim">{today}</span>'
    segs = "".join(f'<span class="st-hub-seg">{s}</span>'
                   for s in (date_seg, llm, hive, agents) if s)
    return f'<div class="st-hub-health">{segs}</div>'


_HUB_LANG_ROW = '''<div class="st-hub-lang-row">
    <select id="st-hub-lang" onchange="var l=this.value;document.cookie='st-lang='+l+';path=/;max-age=31536000';document.body.dataset.stLang=l;document.querySelectorAll('#st-hub [data-'+l+']').forEach(function(e){e.innerHTML=e.getAttribute('data-'+l)});var f=document.getElementById('st-hub-filter');if(f){f.placeholder=f.getAttribute('data-'+l+'-ph')||f.placeholder;}">
      <option value="en" selected>English</option>
      <option value="zh">中文</option>
    </select>
  </div>'''

_HUB_BACK_LINK = ('<a class="st-hub-back" href="/" data-en="← Platform home" '
                  'data-zh="← 返回首页">← Platform home</a>')


def _hub_shell(header: str, body: str, back: bool = False) -> str:
    """Shared scaffold for the hub pages (`/`, `/data`, `/ai`): a 48px top bar
    (brand / back link + lang select) + header block + body, all inside
    #st-hub so the data-en/zh swap JS works."""
    try:
        from importlib.metadata import version
        ver = f'<span class="st-hub-ver">v{version("seatunnel-agent")}</span>'
    except Exception:
        ver = ""
    left = _HUB_BACK_LINK if back else (
        f'<div class="st-hub-brand">SeaTunnel Agent{ver}</div>')
    from seatunnel_agent.hub.registry import _icon_svg
    gear = (f'<a class="st-hub-gear" href="/settings" '
            f'title="Settings">{_icon_svg("settings") or "⚙"}</a>')
    topbar = (f'<div class="st-hub-topbar">{left}'
              f'<div class="st-hub-topbar-right">{gear}{_HUB_LANG_ROW}'
              f'</div></div>')
    try:  # same count the health strip shows — never let it drift
        mark = f'№ {_agent_count()} agents'
    except Exception:
        mark = "SeaTunnel Agent"
    footer = (f'<div class="st-hub-footer"><span>SeaTunnel Agent · '
              f'<a href="{_DOCS_URL}" target="_blank" rel="noopener">docs ↗</a>'
              f'</span><span class="st-hub-mark">{mark}</span></div>')
    return (f'<div class="st-hub" id="st-hub">\n  {topbar}\n'
            f'  <div class="st-hub-header">\n{header}\n  </div>\n'
            f'{body}\n  {footer}\n</div>')


def _build_landing_html() -> str:
    """Root `/` — choose a workspace: Data Agents or AI Platform."""
    header = '''    <div class="st-hub-title" data-en='<span class="st-red">S</span>eaTunnel Agent Platform' data-zh='<span class="st-red">S</span>eaTunnel Agent 工作台'><span class="st-red">S</span>eaTunnel Agent Platform</div>
    <div class="st-hub-subtitle" data-en="Choose a workspace to start" data-zh="选择一个工作区开始">Choose a workspace to start</div>
    <!--STATUS-->'''
    body = '''  <div class="st-hub-section-title st-hub-landing-sec" data-en="Workspaces" data-zh="工作区">Workspaces</div>
  <div class="st-hub-grid">
    <a class="st-hub-card" href="/data">
      <div class="st-hub-logo" style="background:#f76707;">DA</div>
      <div class="st-hub-card-title" data-en="Data Agents" data-zh="数据 Agent 工作区">Data Agents</div>
      <div class="st-hub-card-desc" data-en="Build &amp; govern data pipelines — Text2SQL, SQL review, lineage" data-zh="构建与治理数据管道 — Text2SQL、SQL 审查、血缘">Build &amp; govern data pipelines — Text2SQL, SQL review, lineage</div>
    </a>
    <a class="st-hub-card" href="/ai">
      <div class="st-hub-logo" style="background:#7c3aed;">AI</div>
      <div class="st-hub-card-title" data-en="AI Platform" data-zh="AI 平台">AI Platform</div>
      <div class="st-hub-card-desc" data-en="Engineer the LLM layer — orchestration, eval, prompt lab, cost" data-zh="打磨 LLM 工程 — 编排、评测、Prompt 实验、成本">Engineer the LLM layer — orchestration, eval, prompt lab, cost</div>
    </a>
    <a class="st-hub-card" href="/devops">
      <div class="st-hub-logo" style="background:#0d9488;">DO</div>
      <div class="st-hub-card-title" data-en="DevOps" data-zh="DevOps 工作区">DevOps</div>
      <div class="st-hub-card-desc" data-en="Keep engineering healthy — secret scan, CI triage, dependencies" data-zh="守护工程健康 — 凭证扫描、CI 诊断、依赖体检">Keep engineering healthy — secret scan, CI triage, dependencies</div>
    </a>
  </div>'''
    # cross-cutting engineering tools live right on the landing page
    # (Settings is global config, not a workspace — it lives in the top bar)
    from seatunnel_agent.hub.registry import card_html, workspace_manifests
    by_route = dict(_card_blocks())
    by_route.update({m.route: card_html(m)
                     for m in workspace_manifests("data") if not m.card})
    eng_cards = "".join(by_route[h] for h in _ENG_TOOLS)
    body += (
        '\n  <div class="st-hub-section-title st-hub-landing-sec" '
        'data-en="Engineering Tools" data-zh="工程工具">Engineering Tools</div>'
        f'\n  <div class="st-hub-grid">{eng_cards}</div>')
    return _hub_shell(header, _swap_logos(body)).replace(
        "<!--STATUS-->", _hub_health_html())


def _build_ai_hub_html() -> str:
    """`/ai` — the AI Platform workspace; cards come from plugin manifests."""
    from seatunnel_agent.hub.registry import card_html, workspace_manifests
    header = '''    <div class="st-hub-title" data-en='<span class="st-red">AI</span> Platform' data-zh='<span class="st-red">AI</span> 平台'><span class="st-red">AI</span> Platform</div>
    <div class="st-hub-subtitle" data-en="LLM engineering workspace · orchestrate, evaluate, experiment, observe" data-zh="LLM 工程工作台 · 编排、评测、实验、观测">LLM engineering workspace · orchestrate, evaluate, experiment, observe</div>
    <!--STATUS-->'''
    cards = "\n".join(card_html(m) for m in workspace_manifests("ai"))
    body = ('  <div class="st-hub-grid st-hub-grid-4">\n'
            + cards + '\n  </div>')
    # the AI workspace depends on the LLM config more than anything else —
    # show the same health strip the landing page has
    return _hub_shell(header, body, back=True).replace(
        "<!--STATUS-->", _hub_health_html())


# Data-agent cards grouped into sections on the /data hub; the engineering
# tools are cross-cutting (settings, MCP, UI tests, log inspection) and live
# on the landing page instead.
# group key (from AgentManifest.group) -> section title; order matters
_DATA_GROUPS: list[tuple[str, str, str]] = [
    ("build", "Build & Pipelines", "构建与接入"),
    ("quality", "SQL Quality & Review", "SQL 质量与审查"),
    ("governance", "Lineage & Governance", "血缘与治理"),
]
_ENG_TOOLS = ["/loginspect", "/uitest", "/mcp"]  # /settings lives in the top bar

# instant client-side filter over card titles/descriptions (both languages);
# section titles with no visible card hide themselves
_FILTER_ICO_SVG = ('<svg viewBox="64 64 896 896" focusable="false"><path d="M9'
                   '09.6 854.5L649.9 594.8C690.2 542.7 712 479 712 412c0-80.2-'
                   '31.3-155.4-87.9-212.1-56.6-56.7-132-87.9-212.1-87.9s-155.5'
                   ' 31.3-212.1 87.9C143.2 256.5 112 331.8 112 412c0 80.1 31.3'
                   ' 155.5 87.9 212.1C256.5 680.8 331.8 712 412 712c67 0 130.6'
                   '-21.8 182.7-62l259.7 259.6a8.2 8.2 0 0011.6 0l43.6-43.5a8.'
                   '2 8.2 0 000-11.6zM570.4 570.4C528 612.7 471.8 636 412 636s'
                   '-116-23.3-158.4-65.6C211.3 528 188 471.8 188 412s23.3-116.'
                   '1 65.6-158.4C296 211.3 352.2 188 412 188s116.1 23.2 158.4 '
                   '65.6S636 352.2 636 412s-23.3 116.1-65.6 158.4z"/></svg>')

_HUB_FILTER_ROW = (
    '<div class="st-hub-filter-row"><div class="st-hub-filter-wrap">'
    f'<span class="st-hub-filter-ico">{_FILTER_ICO_SVG}</span>'
    '<span class="st-hub-filter-kbd">/</span>'
    '<input id="st-hub-filter" type="search" '
    'data-en-ph="Filter agents…" data-zh-ph="过滤能力…" placeholder="Filter agents…" '
    'oninput="var q=this.value.toLowerCase();'
    "document.querySelectorAll('#st-hub .st-hub-card').forEach(function(c){"
    "var t=(c.innerText+' '+Array.from(c.querySelectorAll('[data-zh]')).map("
    "function(e){return e.getAttribute('data-zh')+' '+e.getAttribute('data-en')})"
    ".join(' ')).toLowerCase();"
    "c.style.display=(!q||t.indexOf(q)>=0)?'':'none'});"
    "document.querySelectorAll('#st-hub .st-hub-section-title').forEach("
    "function(s){var g=s.nextElementSibling;"
    "var any=g&&Array.from(g.children).some(function(c){"
    "return c.style.display!=='none'});"
    's.style.display=any?\'\':\'none\'});"></div></div>')


# Cards for pages without a manifest (the React uitest page and the
# hub-level Settings page); everything else renders via card_html().
_TOOL_CARDS_HTML = '''
    <a class="st-hub-card" href="/uitest">
      <div class="st-hub-logo" style="background:#f59e0b;">UT</div>
      <div class="st-hub-card-title" data-en="UI Testing Agent" data-zh="UI 测试 Agent">UI Testing Agent</div>
      <div class="st-hub-card-desc" data-en="Browser-driven regression for the Gradio pages — YAML cases, LLM fuzzy assertions, HTML reports" data-zh="真实浏览器驱动的页面自动回归 — YAML 用例、LLM 模糊断言、HTML 报告">Browser-driven regression for the Gradio pages — YAML cases, LLM fuzzy assertions, HTML reports</div>
      <div class="st-hub-enter" style="color:#f59e0b;" data-en="Enter →" data-zh="进入 →">Enter →</div>
    </a>
    <a class="st-hub-card" href="/settings">
      <div class="st-hub-logo" style="background:#64748b;">⚙</div>
      <div class="st-hub-card-title" data-en="Settings" data-zh="设置">Settings</div>
      <div class="st-hub-card-desc" data-en="Configure the LLM API (provider, key, model, base URL) from the browser — no .env editing" data-zh="在界面上配置 LLM API（提供商 / Key / 模型 / Base URL），无需修改本地 .env">Configure the LLM API (provider, key, model, base URL) from the browser — no .env editing</div>
      <div class="st-hub-enter" style="color:#64748b;" data-en="Enter →" data-zh="进入 →">Enter →</div>
    </a>
'''


def _swap_logos(html: str) -> str:
    """Replace the legacy colored-monogram logo divs in a card HTML literal
    with the vendored antd line icons (keyed by the card's href)."""
    from seatunnel_agent.hub.registry import logo_html
    return re.sub(
        r'(<a class="st-hub-card[^"]*" href="(/[^"]+)">\s*)'
        r'<div class="st-hub-logo"[^>]*>.*?</div>',
        lambda m: m.group(1) + logo_html(m.group(2)),
        html, flags=re.S)


_TOOL_CARDS_HTML = _swap_logos(_TOOL_CARDS_HTML)


def _build_devops_hub_html() -> str:
    """`/devops` — engineering-hygiene workspace; cards from manifests."""
    from seatunnel_agent.hub.registry import card_html, workspace_manifests
    header = '''    <div class="st-hub-title" data-en='<span class="st-red">D</span>evOps' data-zh='<span class="st-red">D</span>evOps 工作区'><span class="st-red">D</span>evOps</div>
    <div class="st-hub-subtitle" data-en="Engineering hygiene · scan, triage, audit, release" data-zh="工程卫生工作台 · 扫描、诊断、体检、发布">Engineering hygiene · scan, triage, audit, release</div>'''
    cards = "\n".join(card_html(m) for m in workspace_manifests("devops"))
    body = ('  <div class="st-hub-grid st-hub-grid-4">\n'
            + cards + '\n  </div>')
    return _hub_shell(header, body, back=True)


def _agent_count() -> int:
    """Agents shown anywhere on the hub: carded manifests, the card-less
    landing tools (loginspect/mcp), and the literal cards (uitest/settings).
    Text2SQL aux pages are routes, not agents."""
    from seatunnel_agent.hub.registry import discover
    ms = discover()
    return (len([m for m in ms if m.card or m.route in _ENG_TOOLS])
            + len(_card_blocks()))


def _card_blocks() -> dict[str, str]:
    """href → card HTML block, extracted from the single literal above."""
    return {href: block for block, href in re.findall(
        r'(<a class="st-hub-card" href="(/[^"]+)">.*?</a>)',
        _TOOL_CARDS_HTML, re.S)}


def _build_data_hub_html() -> str:
    """`/data` — the Data Agents workspace, grouped sections + filter."""
    header = '''    <div class="st-hub-title" data-en='<span class="st-red">D</span>ata Agents' data-zh='<span class="st-red">数</span>据 Agent 工作区'><span class="st-red">D</span>ata Agents</div>
    <div class="st-hub-subtitle" data-en="Data engineering workspace · Choose an agent to start" data-zh="数据工程工作台 · 选择一个能力开始">Data engineering workspace · Choose an agent to start</div>'''
    from seatunnel_agent.hub.registry import card_html, workspace_manifests
    mfs = [m for m in workspace_manifests("data") if m.card]
    parts = [_HUB_FILTER_ROW]
    for key, en, zh in _DATA_GROUPS:
        parts.append(f'<div class="st-hub-section-title" data-en="{en}" '
                     f'data-zh="{zh}">{en}</div>')
        parts.append('<div class="st-hub-grid">'
                     + "".join(card_html(m) for m in mfs if m.group == key)
                     + '</div>')
    return _hub_shell(header, "\n".join(parts), back=True)


# Restore the language chosen in a previous visit — chained after the HTML
# refresh so the swap runs on the fresh markup, not the stale one.
_HUB_LANG_RESTORE_JS = """
() => {
    const m = document.cookie.match(/(?:^|; )st-lang=(zh|en)/);
    const l = m ? m[1] : 'en';
    document.body.dataset.stLang = l;
    const sel = document.getElementById('st-hub-lang');
    if (sel && sel.value !== l) {
        sel.value = l;
        sel.dispatchEvent(new Event('change'));
    }
    // "/" focuses the agent filter (the kbd hint on the input promises it)
    if (!window.__stHubSlash) {
        window.__stHubSlash = true;
        document.addEventListener('keydown', (e) => {
            const f = document.getElementById('st-hub-filter');
            const t = document.activeElement && document.activeElement.tagName;
            if (e.key === '/' && f && t !== 'INPUT' && t !== 'TEXTAREA') {
                e.preventDefault();
                f.focus();
            }
        });
    }
}
"""


def _mount_hub(app: gr.Blocks, builder) -> None:
    """Render a hub page inside the current route: static HTML recomputed on
    every visit (the health strip / card set change without a restart), then
    the saved language preference is re-applied."""
    hub_html = gr.HTML(builder())
    app.load(fn=builder, outputs=[hub_html]).then(fn=None, js=_HUB_LANG_RESTORE_JS)
