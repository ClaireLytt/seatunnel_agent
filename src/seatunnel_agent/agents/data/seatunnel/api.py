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
