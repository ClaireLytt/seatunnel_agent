"""Static-detector benchmark over a labeled SQL corpus (skew-bench).

The corpus (``examples/skew_bench/cases.yaml``) pins, per SQL, the exact
rule-id set the detector must report. Running the detector against it
yields micro precision / recall / F1 plus a per-case failure list, so a
rule tweak shows its whole-corpus effect instead of only the new unit
test — the same instrument the text2sql line has in ``t2s-bench``.

Deterministic: no DB, no LLM.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .detector import detect_skew

DEFAULT_CORPUS = Path("examples/skew_bench/cases.yaml")


@dataclass
class BenchCase:
    case_id: str
    sql: str
    dialect: str = "spark"
    expect: frozenset[str] = frozenset()


@dataclass
class CaseFailure:
    case_id: str
    missed: list[str]        # expected but not reported (false negatives)
    spurious: list[str]      # reported but not expected (false positives)


@dataclass
class BenchResult:
    cases: int = 0
    tp: int = 0
    fp: int = 0
    fn: int = 0
    failures: list[CaseFailure] = field(default_factory=list)
    min_f1: float = 1.0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if (self.tp + self.fp) else 1.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if (self.tp + self.fn) else 1.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if (p + r) else 0.0

    @property
    def passed(self) -> bool:
        return self.f1 >= self.min_f1


def load_corpus(path: str | Path = DEFAULT_CORPUS,
                ) -> tuple[list[BenchCase], float]:
    """(cases, min_f1 gate threshold) from the YAML corpus."""
    import yaml

    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    min_f1 = float((data.get("baseline") or {}).get("min_f1", 1.0))
    cases = [BenchCase(case_id=str(c["id"]), sql=str(c["sql"]),
                       dialect=str(c.get("dialect") or "spark"),
                       expect=frozenset(c.get("expect") or []))
             for c in data.get("cases") or []]
    return cases, min_f1


def run_bench(cases: list[BenchCase], min_f1: float = 1.0) -> BenchResult:
    result = BenchResult(cases=len(cases), min_f1=min_f1)
    for case in cases:
        findings, _ = detect_skew(case.sql, case.dialect, "zh")
        got = {f.key for f in findings if f.key}
        missed = sorted(case.expect - got)
        spurious = sorted(got - case.expect)
        result.tp += len(case.expect & got)
        result.fn += len(missed)
        result.fp += len(spurious)
        if missed or spurious:
            result.failures.append(CaseFailure(case.case_id, missed, spurious))
    return result


def render_bench(result: BenchResult, lang: str = "zh") -> str:
    zh = lang != "en"
    lines = ["## " + ("静态倾斜检测基准" if zh else "Static Skew Detector Benchmark"),
             ""]
    lines.append(
        (f"{result.cases} 例 · precision {result.precision:.3f} · "
         f"recall {result.recall:.3f} · F1 {result.f1:.3f}"
         f"（门槛 {result.min_f1:.3f}）") if zh else
        (f"{result.cases} cases · precision {result.precision:.3f} · "
         f"recall {result.recall:.3f} · F1 {result.f1:.3f} "
         f"(gate {result.min_f1:.3f})"))
    if result.failures:
        lines += ["", "| case | " + ("漏报" if zh else "missed")
                  + " | " + ("误报" if zh else "spurious") + " |",
                  "|---|---|---|"]
        for f in result.failures:
            lines.append(f"| `{f.case_id}` | {', '.join(f.missed) or '-'} "
                         f"| {', '.join(f.spurious) or '-'} |")
    else:
        lines += ["", "✅ " + ("全部用例与期望一致。" if zh
                              else "All cases match expectations.")]
    return "\n".join(lines)
