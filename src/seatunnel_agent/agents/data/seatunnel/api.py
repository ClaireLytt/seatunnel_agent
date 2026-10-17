"""REST API for the SeaTunnel Pipeline Builder React page — FastAPI router.

Mounted unconditionally on the served FastAPI instance after hub launch
(see seatunnel_agent.hub.ui), like the uitest / sql_review routers.

Endpoints (walking skeleton — chat/sessions land in later tickets):
  GET /api/seatunnel/meta — static page metadata: modes, templates
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter(prefix="/api/seatunnel", tags=["seatunnel"])

# the four legacy agent modes; labels mirror the Gradio page's i18n dict
# (seatunnel.ui._I18N mode_* keys) so the React page loses no wording
_MODES: list[dict[str, str]] = [
    {"key": "nl", "en": "Natural Language", "zh": "自然语言描述"},
    {"key": "run", "en": "Run Config", "zh": "运行配置文件"},
    {"key": "validate", "en": "Validate Config", "zh": "验证配置"},
    {"key": "diagnose", "en": "Diagnose Log", "zh": "诊断日志"},
]


@router.get("/meta")
def get_meta() -> dict[str, Any]:
    """Static page metadata: agent modes and pipeline templates."""
    from seatunnel_agent.agents.data.seatunnel.templates import TEMPLATES

    return {
        "modes": _MODES,
        "templates": [
            {
                "name": t.name,
                "description": t.description,
                "category": t.category,
                "parameters": t.parameters,
            }
            for t in TEMPLATES
        ],
        "config_placeholder": "examples/fake_to_console.conf",
    }


# Connection state shared with the chat endpoints (later tickets). Mirrors the
# legacy page's settings_holder: holds the loaded Settings plus the
# settings_store version seen at connect time, so a stale-settings reload can
# be detected before each run (legacy ui.py _handle_submit parity).
CONNECTION: dict[str, Any] = {"settings": None, "version": None}


def _warmup_llm(provider: str) -> None:
    """Pre-import the LLM SDK so the first chat doesn't pay the import cost."""
    try:
        if provider == "anthropic":
            import anthropic  # noqa: F401
        else:
            import openai  # noqa: F401
    except Exception:
        pass


@router.post("/connect")
def connect() -> dict[str, Any]:
    """Load settings and report the genuine connect result (success or failure)."""
    import threading

    from seatunnel_agent.common import config, settings_store

    try:
        settings = config.load_settings()
    except Exception as e:
        CONNECTION["settings"] = None
        CONNECTION["version"] = None
        return {"ok": False, "error": str(e)}

    CONNECTION["settings"] = settings
    CONNECTION["version"] = settings_store.get_version()
    threading.Thread(target=_warmup_llm, args=(settings.llm_provider,), daemon=True).start()
    return {"ok": True, "model": settings.model_name}
