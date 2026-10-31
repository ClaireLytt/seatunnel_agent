"""Optional LLM job review from a config draft.

The deterministic generator writes the HOCON; this layer drafts the
pre-run review — tuning, mode fit, what the placeholders need.
Strictly opt-in and bounded to one call per draft.
"""

from __future__ import annotations

import json

from .generator import ConfigDraft

__all__ = ["job_note"]

_SYSTEM_ZH = (
    "你是 SeaTunnel 作业评审。给定一份自动生成的同步作业草稿 JSON"
    "（源/目标连接器、表与列数、job.mode、已填参数与待替换占位符），"
    "起草运行前评审：占位符各自该填什么、并行度与模式是否合适、该加"
    "哪些可选参数（批量/重试/容错）。只输出评审 markdown 列表，简洁，"
    "不要寒暄。")
_SYSTEM_EN = (
    "You are a SeaTunnel job reviewer. Given an auto-generated sync-job "
    "draft JSON (source/sink connectors, table and column count, "
    "job.mode, filled parameters and placeholders), draft the pre-run "
    "review: what each placeholder needs, whether parallelism and mode "
    "fit, which optional parameters (batching, retries, fault "
    "tolerance) deserve adding. Markdown bullets only, terse.")


def job_note(draft: ConfigDraft, lang: str = "zh") -> str:
    """One LLM call → a pre-run review for this job draft."""
    from seatunnel_agent.common.llm import one_shot

    meta = draft.to_dict()
    meta.pop("hocon_text", None)
    return one_shot("seatunnel_gen", _SYSTEM_ZH, _SYSTEM_EN,
                    json.dumps(meta, ensure_ascii=False), lang)
