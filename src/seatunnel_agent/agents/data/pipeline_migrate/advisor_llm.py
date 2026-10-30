"""Optional LLM rewrite advice for flagged migration risks.

The deterministic assessor says *what* will not migrate mechanically
(UDFs, stored procedures, Oracle joins, shell logic, dynamic SQL);
this layer asks the configured LLM *how* to rewrite it for the
suggested target engine.  Strictly opt-in: nothing here runs unless
the caller passes ``llm=true``, and a missing API key surfaces as the
standard settings error.
"""

from __future__ import annotations

from .assessor import JobAssessment

__all__ = ["rewrite_advice"]

_MAX_SCRIPT_CHARS = 8_000
_MAX_JOBS = 3

_SYSTEM_ZH = (
    "你是数据管道迁移专家。给定一个旧 ETL 脚本、确定性评估出的目标引擎与"
    "风险项，给出迁移改写要点：逐个风险说明在目标引擎上的等价写法，"
    "并给出关键代码草案（SQL 或配置片段）。只输出 markdown，克制、"
    "可执行，不要寒暄。")
_SYSTEM_EN = (
    "You are a data-pipeline migration expert. Given a legacy ETL script, "
    "the deterministically assessed target engine and risk findings, "
    "produce rewrite guidance: for each risk, the equivalent construct on "
    "the target engine, with key code sketches (SQL or config). Markdown "
    "only, terse and actionable.")


def rewrite_advice(job: JobAssessment, script: str, lang: str = "zh") -> str:
    """One LLM call → markdown rewrite guidance for a single risky job."""
    from seatunnel_agent.common.config import load_settings
    from seatunnel_agent.common.llm import LLMClient

    client = LLMClient(load_settings(), agent="pipeline_migrate")
    risks = ", ".join(job.risks) or "-"
    prompt = (f"job: {job.job}\n"
              f"target engine: {job.target}\n"
              f"risk codes: {risks}\n"
              f"script:\n```\n{script[:_MAX_SCRIPT_CHARS]}\n```")
    system = _SYSTEM_ZH if lang == "zh" else _SYSTEM_EN
    resp = client.chat(system, [{"role": "user", "content": prompt}])
    return resp.reply_text.strip()


def advice_for_jobs(jobs: list[JobAssessment],
                    scripts: dict[str, str],
                    lang: str = "zh") -> list[tuple[str, str]]:
    """Rewrite advice for the riskiest jobs (capped to keep cost bounded)."""
    risky = [j for j in jobs if j.risks and j.job in scripts]
    risky.sort(key=lambda j: (-len(j.risks), -j.score, j.job))
    return [(j.job, rewrite_advice(j, scripts[j.job], lang=lang))
            for j in risky[:_MAX_JOBS]]


def collect_scripts(jobs: list[JobAssessment], root=None,
                    fallback: tuple[str, str] | None = None
                    ) -> dict[str, str]:
    """Script texts for the risky jobs — from *root*/job paths, or the
    single pasted script given as ``fallback`` (name, text)."""
    from pathlib import Path

    if root is not None:
        root = Path(root)
        return {j.job: (root / j.job).read_text(encoding="utf-8",
                                                errors="replace")
                for j in jobs if j.risks and (root / j.job).is_file()}
    return {fallback[0]: fallback[1]} if fallback else {}


def render_advice(advice: list[tuple[str, str]], lang: str = "zh") -> str:
    """The shared 'LLM rewrite advice' markdown section."""
    from .i18n import tp

    lines = [f"### {tp(lang, 'rpt_llm_advice')}"]
    for job, text in advice:
        lines.append(f"**`{job}`**")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)
