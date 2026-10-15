"""Retrieval benchmark — the regression gate for hybrid retrieval (PRD §5.3).

A bench file is JSONL, one case per line:

    {"question": "昨天各渠道的成交金额", "tables": ["dwd.dwd_trade_order_di"]}

``tables`` lists every acceptable answer (a question may be served by more
than one table). A case scores Top-1 when the first-ranked table is
acceptable, Top-3 when any of the first three is. The CI gate is
"hybrid must not be worse than keyword-only".
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .matcher import match_tables
from .retrieval import HybridRetriever
from .schema import SchemaStore

MODES = ("keyword", "hybrid")


@dataclass
class BenchCase:
    question: str
    tables: list[str]


@dataclass
class BenchResult:
    mode: str
    total: int = 0
    top1: int = 0
    top3: int = 0
    misses: list[dict] = field(default_factory=list)  # top3 misses

    @property
    def top1_rate(self) -> float:
        return self.top1 / self.total if self.total else 0.0

    @property
    def top3_rate(self) -> float:
        return self.top3 / self.total if self.total else 0.0


def load_bench(path: str | Path) -> list[BenchCase]:
    cases: list[BenchCase] = []
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
        tables = [str(t).strip().lower() for t in raw.get("tables", []) if str(t).strip()]
        if not question or not tables:
            raise ValueError(f"{path}:{i}: 需要 question 和非空 tables")
        cases.append(BenchCase(question=question, tables=tables))
    return cases


def run_bench(
    store: SchemaStore,
    cases: list[BenchCase],
    mode: str = "hybrid",
    retriever: HybridRetriever | None = None,
) -> BenchResult:
    if mode not in MODES:
        raise ValueError(f"mode 只支持 {', '.join(MODES)}")
    if mode == "hybrid" and retriever is None:
        retriever = HybridRetriever(store)

    result = BenchResult(mode=mode, total=len(cases))
    for case in cases:
        if mode == "keyword":
            ranked = match_tables(case.question, store, top_n=3)
        else:
            ranked = retriever.rank(case.question, top_n=3)
        names = [m.table.full_name.lower() for m in ranked]
        expected = set(case.tables)
        if names and names[0] in expected:
            result.top1 += 1
        if any(n in expected for n in names):
            result.top3 += 1
        else:
            result.misses.append({
                "question": case.question,
                "expected": case.tables,
                "got": names,
            })
    return result


def render_bench_report(results: list[BenchResult], lang: str = "zh") -> str:
    """Plain-text comparison table plus top-3 misses."""
    lines: list[str] = []
    header = "模式        Top1        Top3        用例数" if lang == "zh" \
        else "mode        Top1        Top3        cases"
    lines.append(header)
    for r in results:
        lines.append(
            f"{r.mode:<10}  {r.top1_rate:>6.1%}     {r.top3_rate:>6.1%}     {r.total}"
        )
    for r in results:
        if r.misses:
            title = f"\n[{r.mode}] Top3 未命中 ({len(r.misses)}):" if lang == "zh" \
                else f"\n[{r.mode}] top-3 misses ({len(r.misses)}):"
            lines.append(title)
            for miss in r.misses[:20]:
                lines.append(
                    f"  - {miss['question']}  期望 {miss['expected']}  实得 {miss['got']}"
                )
    return "\n".join(lines)
