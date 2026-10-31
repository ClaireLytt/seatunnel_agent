"""Deterministic legacy-ETL migration assessor.

Input: a directory of legacy job scripts (``*.sql`` / ``*.hql`` /
``*.sh`` / ``*.py``), or one pasted script.  Per job it measures what
the script actually does — statements, joins, UDF/TRANSFORM calls,
control flow, external tools (sqoop/datax/hive -e/spark-submit),
streaming markers (kafka/canal) and dialect-specific syntax — and
derives:

* the suggested target engine: plain table-to-table moves → SeaTunnel,
  batch SQL transforms → Spark SQL, streaming inputs → Flink,
  orchestration-only shells → keep in the scheduler;
* an effort size (S / M / L) from a transparent score;
* the risk list — constructs that will not migrate mechanically.

Static analysis only — nothing is executed or connected to.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPT_SUFFIXES = (".sql", ".hql", ".sh", ".py")
TARGETS = ("seatunnel", "spark_sql", "flink", "scheduler")
EFFORTS = ("S", "M", "L")

_STMT_RE = re.compile(r";\s*(?:\n|$)")
_JOIN_RE = re.compile(r"\bjoin\b", re.IGNORECASE)
_UDF_RE = re.compile(
    r"\btransform\s*\(|\badd\s+jar\b|\bcreate\s+(?:temporary\s+)?function\b",
    re.IGNORECASE)
_CTRL_RE = re.compile(r"^\s*(?:if\b|for\b|while\b|case\b|def\b|function\b)",
                      re.IGNORECASE | re.MULTILINE)
_INGEST_RE = re.compile(r"\bsqoop\b|\bdatax\b|\bload\s+data\b", re.IGNORECASE)
_STREAM_RE = re.compile(r"\bkafka\b|\bcanal\b|\bbinlog\b|\bflume\b",
                        re.IGNORECASE)
_SQL_EXEC_RE = re.compile(
    r"\bhive\s+-e\b|\bbeeline\b|\bspark-submit\b|\bspark-sql\b|\bimpala-shell\b",
    re.IGNORECASE)
_WRITE_RE = re.compile(r"\binsert\s+(?:overwrite|into)\b|\bcreate\s+table\b",
                       re.IGNORECASE)
_PRODUCE_RE = re.compile(
    r"\binsert\s+(?:overwrite\s+table|into)\s+([\w.]+)"
    r"|\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?([\w.]+)",
    re.IGNORECASE)
_CONSUME_RE = re.compile(r"\b(?:from|join)\s+([\w.]+)", re.IGNORECASE)
_SQOOP_CONNECT_RE = re.compile(r"--connect\s+(\S+)")
_SQOOP_TABLE_RE = re.compile(r"--table\s+(\S+)")
_SQOOP_TARGET_RE = re.compile(r"--target-dir\s+(\S+)")
# DataX job JSON: reader/writer blocks, jdbcUrl possibly inside a list
_DATAX_URL_RE = re.compile(r'"jdbcUrl"\s*:\s*\[?\s*"([^"]+)"')
_DATAX_TABLE_RE = re.compile(r'"table"\s*:\s*\[?\s*"([^"]+)"')
_DATAX_PATH_RE = re.compile(r'"path"\s*:\s*"([^"]+)"')

# constructs that do not migrate mechanically → risk codes
_RISK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("udf", _UDF_RE),
    ("oracle_join", re.compile(r"\(\+\)")),
    ("vendor_proc", re.compile(
        r"\bexec(?:ute)?\s+\w+|\bbegin\s+transaction\b|\bcursor\b",
        re.IGNORECASE)),
    ("shell_logic", re.compile(
        r"^\s*(?:if\s+\[|for\s+\w+\s+in|while\s+)", re.MULTILINE)),
    ("dynamic_sql", re.compile(r"\$\{hiveconf:|\$\{\w+\}|%\(\w+\)s")),
    ("local_fs", re.compile(r"\blocal\s+(?:directory|inpath)\b|/tmp/",
                            re.IGNORECASE)),
)


@dataclass
class JobAssessment:
    job: str
    kind: str              # "sql" | "shell" | "python"
    lines: int
    statements: int
    joins: int
    target: str
    effort: str
    score: int
    reasons: list[str] = field(default_factory=list)  # i18n codes
    risks: list[str] = field(default_factory=list)    # i18n codes
    produces: list[str] = field(default_factory=list)  # tables written
    consumes: list[str] = field(default_factory=list)  # tables read
    stub: str = ""  # SeaTunnel config skeleton (plain-sync sqoop jobs)

    def to_dict(self) -> dict[str, Any]:
        return {"job": self.job, "kind": self.kind, "lines": self.lines,
                "statements": self.statements, "joins": self.joins,
                "target": self.target, "effort": self.effort,
                "score": self.score, "reasons": list(self.reasons),
                "risks": list(self.risks),
                "produces": list(self.produces),
                "consumes": list(self.consumes),
                "stub": self.stub}


def _kind(name: str) -> str:
    suffix = Path(name).suffix.lower()
    if suffix in (".sql", ".hql"):
        return "sql"
    if suffix == ".py":
        return "python"
    if suffix == ".json":
        return "datax"
    return "shell"


def assess_job(name: str, text: str) -> JobAssessment:
    kind = _kind(name)
    if kind == "datax":
        return _assess_datax(name, text)
    lines = len([ln for ln in text.splitlines() if ln.strip()])
    statements = len(_STMT_RE.findall(text)) or (1 if text.strip() else 0)
    joins = len(_JOIN_RE.findall(text))
    ctrl = len(_CTRL_RE.findall(text)) if kind != "sql" else 0
    risks = [code for code, pat in _RISK_PATTERNS if pat.search(text)]

    ingest = bool(_INGEST_RE.search(text))
    stream = bool(_STREAM_RE.search(text))
    writes = bool(_WRITE_RE.search(text))
    runs_sql = bool(_SQL_EXEC_RE.search(text)) or kind == "sql"

    reasons: list[str] = []
    if stream:
        target = "flink"
        reasons.append("streaming_source")
    elif ingest and joins == 0:
        target = "seatunnel"
        reasons.append("plain_sync")
    elif runs_sql and (writes or joins):
        target = "spark_sql"
        reasons.append("batch_sql")
    elif kind in ("shell", "python") and not runs_sql:
        target = "scheduler"
        reasons.append("orchestration_only")
    else:
        target = "spark_sql"
        reasons.append("batch_sql")

    score = (statements + 2 * joins + 2 * ctrl + 3 * len(risks)
             + lines // 50)
    effort = "S" if score < 8 else ("M" if score < 20 else "L")
    produces = sorted({m.group(1) or m.group(2)
                       for m in _PRODUCE_RE.finditer(text)})
    consumes = sorted({m.group(1) for m in _CONSUME_RE.finditer(text)}
                      - set(produces))
    stub = _seatunnel_stub(text) if target == "seatunnel" else ""
    return JobAssessment(job=name, kind=kind, lines=lines,
                         statements=statements, joins=joins, target=target,
                         effort=effort, score=score, reasons=reasons,
                         risks=risks, produces=produces, consumes=consumes,
                         stub=stub)


def _assess_datax(name: str, text: str) -> JobAssessment:
    """DataX reader/writer job → SeaTunnel, with the config skeleton."""
    lines = len([ln for ln in text.splitlines() if ln.strip()])
    url = _DATAX_URL_RE.search(text)
    table = _DATAX_TABLE_RE.search(text)
    path = _DATAX_PATH_RE.search(text)
    stub = ""
    if url and table:
        sink = ("\n".join(["sink {", "  HdfsFile {",
                           f'    path = "{path.group(1)}"',
                           '    file_format_type = "orc"', "  }", "}"])
                if path else
                "sink {\n  # fill in: the warehouse sink "
                "(Hive / Doris / Jdbc ...)\n}")
        stub = "\n".join([
            "env {", "  parallelism = 2", '  job.mode = "BATCH"', "}", "",
            "source {", "  Jdbc {",
            f'    url = "{url.group(1)}"',
            '    driver = "com.mysql.cj.jdbc.Driver"',
            '    user = "<user>"', '    password = "<password>"',
            f'    query = "SELECT * FROM {table.group(1)}"',
            "  }", "}", "", sink])
    risks = ["dynamic_sql"] if "${" in text else []
    score = 1 + 3 * len(risks) + lines // 50
    return JobAssessment(
        job=name, kind="datax", lines=lines, statements=1, joins=0,
        target="seatunnel", effort="S" if score < 8 else "M", score=score,
        reasons=["plain_sync"], risks=risks, stub=stub)


def _seatunnel_stub(text: str) -> str:
    """Sqoop import args → SeaTunnel Jdbc-to-HdfsFile skeleton."""
    connect = _SQOOP_CONNECT_RE.search(text)
    table = _SQOOP_TABLE_RE.search(text)
    if not (connect and table):
        return ""
    target = _SQOOP_TARGET_RE.search(text)
    sink_path = target.group(1) if target else "<target-dir>"
    return "\n".join([
        "env {", "  parallelism = 2", '  job.mode = "BATCH"', "}", "",
        "source {", "  Jdbc {",
        f'    url = "{connect.group(1)}"',
        '    driver = "com.mysql.cj.jdbc.Driver"',
        '    user = "<user>"', '    password = "<password>"',
        f'    query = "SELECT * FROM {table.group(1)}"',
        "  }", "}", "",
        "sink {", "  HdfsFile {",
        f'    path = "{sink_path}"',
        '    file_format_type = "orc"',
        "  }", "}"])


@dataclass
class MigrationReport:
    jobs: list[JobAssessment] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    migration_order: list[list[str]] = field(default_factory=list)  # job waves
    shared_tables: list[dict[str, Any]] = field(default_factory=list)
    # job-dependency graph, effort score as duration — paste into the
    # DAG optimizer to plan the migration itself ("how long with k people")
    migration_dag: dict[str, Any] = field(default_factory=dict)

    def counts(self) -> dict[str, int]:
        out = dict.fromkeys(TARGETS, 0)
        for job in self.jobs:
            out[job.target] += 1
        return out

    def effort_counts(self) -> dict[str, int]:
        out = dict.fromkeys(EFFORTS, 0)
        for job in self.jobs:
            out[job.effort] += 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {"jobs": [j.to_dict() for j in self.jobs],
                "counts": self.counts(),
                "efforts": self.effort_counts(),
                "warnings": list(self.warnings),
                "migration_order": [list(w) for w in self.migration_order],
                "shared_tables": [dict(s) for s in self.shared_tables],
                "migration_dag": dict(self.migration_dag)}


def assess_text(name: str, text: str) -> MigrationReport:
    if not (text or "").strip():
        raise ValueError("empty script")
    return MigrationReport(jobs=[assess_job(name or "pasted.sql", text)])


def assess_dir(root: str | Path) -> MigrationReport:
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f"not a directory: {root}")
    report = MigrationReport()
    suffixes = SCRIPT_SUFFIXES + (".json",)
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            report.warnings.append(f"{path.name}: {exc}")
            continue
        if path.suffix.lower() == ".json" and '"reader"' not in text:
            continue  # not a DataX job definition
        report.jobs.append(
            assess_job(str(path.relative_to(root)).replace("\\", "/"), text))
    if not report.jobs:
        raise ValueError(f"no scripts ({', '.join(SCRIPT_SUFFIXES)}) "
                         f"under: {root}")
    # migrate the easy wins first
    report.jobs.sort(key=lambda j: (j.score, j.job))
    _link_jobs(report)
    return report


def _link_jobs(report: MigrationReport) -> None:
    """Table-level deps between jobs → migration waves + shared tables."""
    producer: dict[str, str] = {}
    for job in report.jobs:
        for table in job.produces:
            producer[table.lower()] = job.job
    deps: dict[str, set[str]] = {j.job: set() for j in report.jobs}
    for job in report.jobs:
        for table in job.consumes:
            up = producer.get(table.lower())
            if up and up != job.job:
                deps[job.job].add(up)
                entry = next((s for s in report.shared_tables
                              if s["table"] == table.lower()), None)
                if entry is None:
                    entry = {"table": table.lower(), "producer": up,
                             "consumers": []}
                    report.shared_tables.append(entry)
                entry["consumers"].append(job.job)
    # Kahn waves: produce-side jobs migrate before their consumers
    remaining = dict(deps)
    while remaining:
        wave = sorted(j for j, ups in remaining.items()
                      if not ups & set(remaining))
        if not wave:
            report.warnings.append(
                "dependency cycle between jobs: "
                + ", ".join(sorted(remaining)))
            break
        report.migration_order.append(wave)
        for j in wave:
            del remaining[j]
    report.shared_tables.sort(key=lambda s: s["table"])
    report.migration_dag = {"tasks": [
        {"name": j.job, "deps": sorted(deps[j.job]),
         "duration": max(j.score, 1)}
        for j in sorted(report.jobs, key=lambda j: j.job)]}
