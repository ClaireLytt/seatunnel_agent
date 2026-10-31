"""REST API for the mock-data generator — FastAPI router.

  POST /api/mockdata/generate — column strategies + generated rows
  GET  /api/mockdata/health — health check
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from seatunnel_agent.common.api_factory import make_text_router

from .generator import generate_mock
from .report import render_markdown

_ENV = "MOCKDATA_API_ALLOWED_DIRS"


class GenerateRequest(BaseModel):
    data_file: str | None = Field(
        None, description="Sample CSV/JSONL file (whitelisted dirs)")
    data_text: str = Field("", description="Inline sample rows: CSV with "
                                           "a header, or JSONL")
    count: int = Field(50, description="Rows to generate (1..10000)")
    seed: int = Field(42, description="Random seed; same sample + seed = "
                                      "same rows")
    llm: bool = Field(
        False, description="Also draft a dataset note via the configured "
                           "LLM (needs an API key; strategies only, "
                           "never the rows)")
    lang: str = Field("zh", description="Report language: 'zh' or 'en'")
    report: bool = Field(False, description="Include the rendered markdown report")


def _core(req: GenerateRequest, resolve):
    from seatunnel_agent.agents.data.sample_profile import parse_rows

    raw = resolve(req.data_file, req.data_text,
                  "'data_file' or 'data_text'")
    headers, rows = parse_rows(raw)
    return generate_mock(headers, rows, count=req.count, seed=req.seed)


def _llm(req: GenerateRequest, result, lang: str):
    from .advisor_llm import dataset_note
    from .i18n import tp

    note = dataset_note(result, lang=lang)
    return ("dataset_note", note,
            f"### {tp(lang, 'rpt_llm_note')}\n{note}\n")


router = make_text_router(
    prefix="/api/mockdata", tags=["mock_data"],
    endpoint="generate", request_model=GenerateRequest,
    health_name="mock_data", env_var=_ENV,
    core=_core,
    render=lambda result, req, lang: render_markdown(result, lang=lang),
    llm=_llm,
)
