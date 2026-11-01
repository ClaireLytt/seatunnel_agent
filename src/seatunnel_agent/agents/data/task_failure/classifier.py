"""Deterministic failure attribution over a scheduler's failed-task export.

Input is the failed-task listing — CSV with a header or a JSON list::

    [{"task": "dwd_orders", "dag": "daily_core",
      "error": "FileNotFoundException: partition dt=2026-10-30 ...",
      "retries": 2, "final_status": "failed"}]

Every failure is classified by its error text (dependency missing /
resource / data error / timeout / connection / code error / other),
graded for whether retrying helped (a retry that eventually succeeded
marks the cause transient; retries that kept failing mark retrying
futile for that cause), and clustered by (class, normalized error
signature) so one root cause shows up as one group however many tasks
it broke.  Each class carries a prescription pointing at the sibling
agent that digs deeper.  No scheduler connection.
"""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field

__all__ = ["FailedTask", "FailureCluster", "FailureResult",
           "classify_failures", "parse_failures"]

_CLASSES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("dependency_missing", re.compile(
        r"(upstream|dependen|not\s+found|no\s+such|missing|partition.*"
        r"(miss|not)|filenotfound|does not exist|等待上游|上游未就绪)",
        re.IGNORECASE)),
    ("resource", re.compile(
        r"(outofmemory|oom|memory limit|killed|container|yarn|quota|"
        r"disk.*(full|space)|slots?|资源不足|内存)", re.IGNORECASE)),
    ("timeout", re.compile(r"(time.?out|deadline|expired|超时)",
                           re.IGNORECASE)),
    ("connection", re.compile(
        r"(connect|refused|reset|unreachable|broken pipe|eof|网络)",
        re.IGNORECASE)),
    ("data_error", re.compile(
        r"(parse|cast|schema|column|null.*constraint|duplicate|malformed|"
        r"corrupt|encoding|脏数据|类型)", re.IGNORECASE)),
    ("code_error", re.compile(
        r"(traceback|exception|nullpointer|nameerror|syntaxerror|"
        r"indexerror|keyerror|assert)", re.IGNORECASE)),
)

_SIG_NOISE = re.compile(r"[\d/:\\.\-_']+")


@dataclass
class FailedTask:
    task: str
    dag: str = ""
    error: str = ""
    retries: int = 0
    final_status: str = "failed"

    def to_dict(self) -> dict:
        return {"task": self.task, "dag": self.dag,
                "error": self.error[:200], "retries": self.retries,
                "final_status": self.final_status}


@dataclass
class FailureCluster:
    cause: str
    signature: str
    tasks: list[str] = field(default_factory=list)
    sample_error: str = ""
    retried: int = 0
    retry_recovered: int = 0

    @property
    def retry_verdict(self) -> str:
        if not self.retried:
            return "untried"
        if self.retry_recovered == self.retried:
            return "transient"
        if self.retry_recovered == 0:
            return "futile"
        return "mixed"

    def to_dict(self) -> dict:
        return {"cause": self.cause, "signature": self.signature,
                "count": len(self.tasks), "tasks": self.tasks[:8],
                "sample_error": self.sample_error[:160],
                "retried": self.retried,
                "retry_recovered": self.retry_recovered,
                "retry_verdict": self.retry_verdict}


@dataclass
class FailureResult:
    total: int
    causes: dict[str, int]
    clusters: list[FailureCluster]

    def to_dict(self) -> dict:
        return {"total": self.total, "causes": self.causes,
                "clusters": [c.to_dict() for c in self.clusters]}


def parse_failures(text: str) -> list[FailedTask]:
    body = (text or "").strip()
    if not body:
        raise ValueError("empty export / 导出为空")
    if body.startswith("["):
        items = json.loads(body)
    else:
        items = [dict(r) for r in csv.DictReader(io.StringIO(body))]
    tasks: list[FailedTask] = []
    for i, it in enumerate(items, start=1):
        if not isinstance(it, dict) or not (it.get("task") or "").strip():
            raise ValueError(f"row {i}: needs 'task' / 第 {i} 行缺 task")
        tasks.append(FailedTask(
            task=str(it["task"]).strip(),
            dag=str(it.get("dag") or "").strip(),
            error=str(it.get("error") or "").strip(),
            retries=int(float(it.get("retries") or 0)),
            final_status=str(it.get("final_status")
                             or "failed").strip().lower()))
    if not tasks:
        raise ValueError("no failed tasks / 没有失败任务")
    return tasks


def _cause_of(error: str) -> str:
    for name, pat in _CLASSES:
        if pat.search(error):
            return name
    return "other"


def _signature(error: str) -> str:
    sig = _SIG_NOISE.sub(" ", error.lower())
    return " ".join(sig.split())[:60]


def classify_failures(tasks: list[FailedTask]) -> FailureResult:
    clusters: dict[tuple[str, str], FailureCluster] = {}
    causes: dict[str, int] = {}
    for t in tasks:
        cause = _cause_of(t.error)
        causes[cause] = causes.get(cause, 0) + 1
        key = (cause, _signature(t.error))
        cl = clusters.get(key)
        if cl is None:
            cl = clusters[key] = FailureCluster(
                cause=cause, signature=key[1], sample_error=t.error)
        cl.tasks.append(t.task)
        if t.retries > 0:
            cl.retried += 1
            if t.final_status == "success":
                cl.retry_recovered += 1
    ordered = sorted(clusters.values(),
                     key=lambda c: (-len(c.tasks), c.cause))
    causes = dict(sorted(causes.items(), key=lambda kv: (-kv[1], kv[0])))
    return FailureResult(total=len(tasks), causes=causes,
                         clusters=ordered)
