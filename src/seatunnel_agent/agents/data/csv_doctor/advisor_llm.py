"""Optional LLM incident note from a CSV diagnosis.

The deterministic doctor repairs the file; this layer drafts the note
back to the producing side.  Strictly opt-in and bounded to one call
per diagnosis.  Only finding metadata is sent — never the rows.
"""

from __future__ import annotations

import json

from .doctor import CsvDoctorReport

__all__ = ["incident_note"]

_SYSTEM_ZH = (
    "你是数据接入负责人。给定一份 CSV 急救诊断的元数据 JSON（分隔符、行列"
    "数、各诊断项与数量 — 不含数据行），起草发回文件生产方的事故说明：各"
    "问题的根因在导出侧还是传输侧、生产方要改什么（编码/引号/列数）、哪些"
    "损失（U+FFFD）必须重新导出。只输出说明 markdown，简洁，不要寒暄。")
_SYSTEM_EN = (
    "You are the data-ingestion owner. Given the metadata JSON of a CSV "
    "triage (delimiter, shape, findings with counts — no rows "
    "included), draft the incident note back to the producing side: "
    "whether each problem's root cause is the export or the transport, "
    "what the producer must change (encoding, quoting, column counts), "
    "and which losses (U+FFFD) demand a re-export. Markdown only, "
    "terse.")


def incident_note(report: CsvDoctorReport, lang: str = "zh") -> str:
    """One LLM call → an incident note; rows never leave the process."""
    from seatunnel_agent.common.llm import one_shot

    meta = report.to_dict()
    meta.pop("fixed_csv", None)
    return one_shot("csv_doctor", _SYSTEM_ZH, _SYSTEM_EN,
                    json.dumps(meta, ensure_ascii=False), lang)
