"""End-to-end Text2SQL evaluation — question → agent → result vs golden SQL.

The retrieval bench (bench.py) only measures table matching; this harness
measures the whole pipeline: each case's *golden SQL* is executed directly
against the database, the agent answers the natural-language question with
a real LLM, and the two result sets are compared order-insensitively with
float tolerance. Accuracy = exactly-matching result sets.

Dataset: JSONL, one case per line:

    {"question": "各城市的销售额", "golden_sql": "SELECT city, SUM(amount) ..."}

Run: ``seatunnel-agent t2s-eval --dataset ... --ddl ... --ds-type sqlite
--database ...`` (needs an LLM API key; ``--limit`` caps cost while trying
it out). The report shows accuracy plus per-case diffs, so failures are
diagnosable — and multi-model comparison is just re-running with
``--model``/``--provider``.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from .executor import DatabaseConfig, create_executor
from .schema import SchemaStore

_FLOAT_TOL = 1e-6


@dataclass
class EvalCase:
    question: str
    golden_sql: str


@dataclass
class CaseResult:
    question: str
    status: str            # "pass" | "fail" | "error"
    agent_sql: str = ""
    detail: str = ""
    elapsed_ms: int = 0


@dataclass
class EvalReport:
    cases: list[CaseResult] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.cases)

    @property
    def passed(self) -> int:
        return sum(1 for c in self.cases if c.status == "pass")

    @property
    def accuracy(self) -> float:
        return self.passed / self.total if self.total else 0.0


def load_dataset(path: str | Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for i, line in enumerate(
        Path(path).read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{i}: 无效 JSON: {exc}") from exc
        question = str(raw.get("question", "")).strip()
        golden = str(raw.get("golden_sql", "")).strip()
        if not question or not golden:
            raise ValueError(f"{path}:{i}: 需要 question 和 golden_sql")
        cases.append(EvalCase(question=question, golden_sql=golden))
    return cases


def _norm_cell(v: Any) -> Any:
    """Comparable cell: floats rounded, everything else stringified."""
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        f = float(v)
        return round(f, 6)
    s = str(v).strip()
    try:  # numeric strings compare as numbers ("5" == 5.0)
        return round(float(s), 6)
    except ValueError:
        return s


def results_match(
    golden_rows: list[tuple], agent_rows: list[tuple],
) -> tuple[bool, str]:
    """Order-insensitive result-set comparison with float tolerance.

    Column names are ignored (aliases legitimately differ); the agent may
    return extra columns as long as the golden columns appear as a prefix
    — LIMIT-injected ordering differences are handled by sorting.
    """
    def _norm(rows: list[tuple], width: int | None = None) -> list[tuple]:
        out = []
        for r in rows:
            cells = tuple(_norm_cell(v) for v in r)
            if width is not None:
                cells = cells[:width]
            out.append(cells)
        return sorted(out, key=lambda t: tuple(str(c) for c in t))

    width = len(golden_rows[0]) if golden_rows else None
    g = _norm(golden_rows)
    a = _norm(agent_rows, width)
    if g == a:
        return True, ""
    missing = [r for r in g if r not in a][:3]
    extra = [r for r in a if r not in g][:3]
    return False, (
        f"golden {len(g)} rows vs agent {len(a)} rows; "
        f"missing={missing} extra={extra}"
    )


AgentRunner = Callable[[str], tuple[str, list[tuple]]]
"""question -> (generated_sql, result_rows); raises on agent failure."""


def make_agent_runner(
    settings,
    store: SchemaStore,
    ds_type: str,
    db_config: DatabaseConfig,
    metric_store=None,
) -> AgentRunner:
    """Real-LLM runner: one fresh agent per question (no history leakage)."""

    def _run(question: str) -> tuple[str, list[tuple]]:
        from .agent import Text2SQLAgent

        agent = Text2SQLAgent(
            settings, store=store, ds_type=ds_type, db_config=db_config,
            metric_store=metric_store,
        )
        agent.run(question)
        rt = agent.runtime
        if rt.last_result is None:
            raise RuntimeError("agent produced no query result")
        return rt.last_sql, [tuple(r) for r in rt.last_result.rows]

    return _run


def run_eval(
    cases: list[EvalCase],
    agent_runner: AgentRunner,
    db_config: DatabaseConfig,
    store: SchemaStore | None = None,
) -> EvalReport:
    """Evaluate every case; agent exceptions become status='error'."""
    from .validator import validate_sql

    executor = create_executor(db_config)
    report = EvalReport()
    for case in cases:
        t0 = time.time()
        result = CaseResult(question=case.question, status="error")
        try:
            if store is not None:
                validation = validate_sql(case.golden_sql, store)
                if not validation.ok:
                    result.detail = ("golden SQL rejected: "
                                     + "; ".join(validation.errors))
                    report.cases.append(result)
                    continue
            golden = executor.run(case.golden_sql, max_rows=1000)
        except Exception as exc:
            result.detail = f"golden SQL failed: {exc}"
            report.cases.append(result)
            continue
        try:
            agent_sql, agent_rows = agent_runner(case.question)
            result.agent_sql = agent_sql
        except Exception as exc:
            result.detail = f"agent failed: {exc}"
            result.elapsed_ms = int((time.time() - t0) * 1000)
            report.cases.append(result)
            continue
        ok, diff = results_match([tuple(r) for r in golden.rows], agent_rows)
        result.status = "pass" if ok else "fail"
        result.detail = diff
        result.elapsed_ms = int((time.time() - t0) * 1000)
        report.cases.append(result)
    return report


def render_eval_report(report: EvalReport, model_name: str = "") -> str:
    lines = ["# Text2SQL 端到端评测报告", ""]
    if model_name:
        lines.append(f"> 模型: {model_name}")
    lines.append(
        f"**准确率 {report.accuracy:.1%}** "
        f"({report.passed}/{report.total} 通过)"
    )
    fails = [c for c in report.cases if c.status != "pass"]
    if fails:
        lines.append("")
        lines.append("## 未通过用例")
        for c in fails:
            lines.append("")
            lines.append(f"- **{c.question}** [{c.status}]")
            if c.agent_sql:
                lines.append(f"  - agent SQL: `{c.agent_sql}`")
            lines.append(f"  - {c.detail}")
    return "\n".join(lines)
