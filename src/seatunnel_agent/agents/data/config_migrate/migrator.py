# -*- coding: utf-8 -*-
"""DataX / Sqoop → SeaTunnel config migration (deterministic).

Same philosophy as sql_transpile: a rule-based converter that always
produces something reviewable — the parts it can map become SeaTunnel
HOCON, everything it cannot becomes a structured Issue (never silently
dropped). No LLM, no network, no database connection.
"""

from __future__ import annotations

import json
import re
import shlex
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LEVELS = ("error", "warn", "info")

# ── plugin registries ──

_JDBC_DRIVERS = {
    "mysql": "com.mysql.cj.jdbc.Driver",
    "postgresql": "org.postgresql.Driver",
    "sqlserver": "com.microsoft.sqlserver.jdbc.SQLServerDriver",
    "oracle": "oracle.jdbc.OracleDriver",
}

_JDBC_READERS = {"mysqlreader": "mysql", "postgresqlreader": "postgresql",
                 "sqlserverreader": "sqlserver", "oraclereader": "oracle"}
_JDBC_WRITERS = {"mysqlwriter": "mysql", "postgresqlwriter": "postgresql",
                 "sqlserverwriter": "sqlserver", "oraclewriter": "oracle"}


@dataclass
class Issue:
    level: str            # error | warn | info
    kind: str
    params: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"level": self.level, "kind": self.kind,
                "params": dict(self.params)}


@dataclass
class MigrateResult:
    source_path: str
    source_kind: str                  # datax | sqoop
    output_conf: str                  # SeaTunnel HOCON (may contain TODOs)
    issues: list[Issue] = field(default_factory=list)
    reader: str = ""
    writer: str = ""
    elapsed_ms: int = 0

    @property
    def ok(self) -> bool:
        return all(i.level != "error" for i in self.issues)

    def worst_level(self) -> str | None:
        levels = {i.level for i in self.issues}
        for lv in LEVELS:
            if lv in levels:
                return lv
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_path": self.source_path,
            "source_kind": self.source_kind,
            "reader": self.reader, "writer": self.writer,
            "ok": self.ok,
            "output_conf": self.output_conf,
            "issues": [i.to_dict() for i in self.issues],
            "elapsed_ms": self.elapsed_ms,
        }


def _hocon_value(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    return json.dumps(str(v), ensure_ascii=False)


def _hocon_block(name: str, params: dict[str, Any], indent: int = 2) -> str:
    pad = " " * indent
    lines = [f"{pad}{name} {{"]
    for k, v in params.items():
        if v is None or v == "":
            continue
        if k.startswith("#"):
            # keys starting with '#' render as comments (TODO markers)
            lines.append(f"{pad}  # {v}")
        else:
            key = k if re.fullmatch(r"[\w.-]+", k) else json.dumps(k)
            lines.append(f"{pad}  {key} = {_hocon_value(v)}")
    lines.append(f"{pad}}}")
    return "\n".join(lines)


def render_conf(env: dict[str, Any], source: tuple[str, dict[str, Any]],
                sink: tuple[str, dict[str, Any]]) -> str:
    return "\n\n".join([
        _hocon_block("env", env, 0).replace("env {", "env {", 1),
        "source {\n" + _hocon_block(source[0], source[1]) + "\n}",
        "sink {\n" + _hocon_block(sink[0], sink[1]) + "\n}",
    ]) + "\n"


# ── DataX ──

def _first(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _datax_jdbc_source(kind: str, param: dict[str, Any],
                       issues: list[Issue]) -> dict[str, Any]:
    conn = _first(param.get("connection")) or {}
    url = _first(conn.get("jdbcUrl")) or ""
    if isinstance(param.get("connection"), list) and len(param["connection"]) > 1:
        issues.append(Issue("warn", "multi_connection",
                            {"n": str(len(param["connection"]))}))
    query = _first(param.get("querySql"))
    if not query:
        table = _first(conn.get("table")) or ""
        cols = param.get("column") or ["*"]
        col_sql = ", ".join(str(c) for c in cols)
        query = f"select {col_sql} from {table}"
        if param.get("where"):
            query += f" where {param['where']}"
        if isinstance(conn.get("table"), list) and len(conn["table"]) > 1:
            issues.append(Issue("warn", "multi_table",
                                {"n": str(len(conn["table"]))}))
    out: dict[str, Any] = {
        "url": url,
        "driver": _JDBC_DRIVERS[kind],
        "user": param.get("username", ""),
        "password": param.get("password", ""),
        "query": query,
    }
    if param.get("splitPk"):
        out["partition_column"] = param["splitPk"]
        issues.append(Issue("info", "split_pk", {"col": param["splitPk"]}))
    return out


def _datax_jdbc_sink(kind: str, param: dict[str, Any],
                     issues: list[Issue]) -> dict[str, Any]:
    conn = _first(param.get("connection")) or {}
    url = _first(conn.get("jdbcUrl")) or conn.get("jdbcUrl") or ""
    table = _first(conn.get("table")) or ""
    m = re.search(r"jdbc:\w+://[^/]+/(\w+)", str(url))
    database = m.group(1) if m else ""
    if not database:
        issues.append(Issue("warn", "no_database", {"url": str(url)[:80]}))
    out: dict[str, Any] = {
        "url": url,
        "driver": _JDBC_DRIVERS[kind],
        "user": param.get("username", ""),
        "password": param.get("password", ""),
        "generate_sink_sql": True,
        "database": database,
        "table": table,
    }
    if param.get("writeMode") and param["writeMode"] != "insert":
        issues.append(Issue("warn", "write_mode",
                            {"mode": str(param["writeMode"])}))
    for hook in ("preSql", "postSql"):
        if param.get(hook):
            issues.append(Issue("warn", "pre_post_sql", {"hook": hook}))
    return out


def _datax_source(name: str, param: dict[str, Any],
                  issues: list[Issue]) -> tuple[str, dict[str, Any]]:
    if name in _JDBC_READERS:
        return "Jdbc", _datax_jdbc_source(_JDBC_READERS[name], param, issues)
    if name == "streamreader":
        issues.append(Issue("info", "stream_reader", {}))
        return "FakeSource", {"row.num": param.get("sliceRecordCount", 16)}
    if name == "txtfilereader":
        return "LocalFile", {
            "path": _first(param.get("path")) or "",
            "file_format_type": "text" if param.get("fieldDelimiter")
            else "text",
            "field_delimiter": param.get("fieldDelimiter", ","),
        }
    if name == "hdfsreader":
        return "HdfsFile", {
            "path": param.get("path", ""),
            "fs.defaultFS": param.get("defaultFS", ""),
            "file_format_type": param.get("fileType", "text"),
        }
    issues.append(Issue("error", "unknown_reader", {"name": name}))
    return "TODO_Source", {"# TODO": f"unsupported DataX reader: {name}"}


def _datax_sink(name: str, param: dict[str, Any],
                issues: list[Issue]) -> tuple[str, dict[str, Any]]:
    if name in _JDBC_WRITERS:
        return "Jdbc", _datax_jdbc_sink(_JDBC_WRITERS[name], param, issues)
    if name == "streamwriter":
        return "Console", {}
    if name == "doriswriter":
        fe = _first(param.get("feLoadUrl") or param.get("loadUrl")) or ""
        return "Doris", {
            "fenodes": fe,
            "username": param.get("username", ""),
            "password": param.get("password", ""),
            "table.identifier":
                f"{param.get('database', '')}.{param.get('table', '')}",
        }
    if name == "starrockswriter":
        return "StarRocks", {
            "nodeUrls": _first(param.get("loadUrl")) or "",
            "username": param.get("username", ""),
            "password": param.get("password", ""),
            "database": param.get("database", ""),
            "table": param.get("table", ""),
        }
    if name == "hdfswriter":
        return "HdfsFile", {
            "path": param.get("path", ""),
            "fs.defaultFS": param.get("defaultFS", ""),
            "file_format_type": param.get("fileType", "text"),
        }
    if name == "txtfilewriter":
        return "LocalFile", {
            "path": param.get("path", ""),
            "file_format_type": "text",
        }
    issues.append(Issue("error", "unknown_writer", {"name": name}))
    return "TODO_Sink", {"# TODO": f"unsupported DataX writer: {name}"}


def migrate_datax(text: str, source_path: str = "<inline>") -> MigrateResult:
    """One DataX job JSON → one SeaTunnel config."""
    t0 = time.time()
    issues: list[Issue] = []
    try:
        job = json.loads(text)
    except json.JSONDecodeError as e:
        return MigrateResult(
            source_path=source_path, source_kind="datax", output_conf="",
            issues=[Issue("error", "bad_json", {"error": str(e)})],
            elapsed_ms=int((time.time() - t0) * 1000))

    content = _first((job.get("job") or {}).get("content")) or {}
    if isinstance((job.get("job") or {}).get("content"), list) \
            and len(job["job"]["content"]) > 1:
        issues.append(Issue("warn", "multi_content",
                            {"n": str(len(job["job"]["content"]))}))
    reader = (content.get("reader") or {})
    writer = (content.get("writer") or {})
    rname = str(reader.get("name", "")).lower()
    wname = str(writer.get("name", "")).lower()
    if not rname or not wname:
        issues.append(Issue("error", "not_datax", {}))
        return MigrateResult(
            source_path=source_path, source_kind="datax", output_conf="",
            issues=issues, elapsed_ms=int((time.time() - t0) * 1000))

    source = _datax_source(rname, reader.get("parameter") or {}, issues)
    sink = _datax_sink(wname, writer.get("parameter") or {}, issues)

    env: dict[str, Any] = {"job.mode": "BATCH"}
    speed = ((job.get("job") or {}).get("setting") or {}).get("speed") or {}
    if speed.get("channel"):
        env["parallelism"] = int(speed["channel"])
    err = ((job.get("job") or {}).get("setting") or {}).get("errorLimit")
    if err:
        issues.append(Issue("info", "error_limit", {"conf": json.dumps(err)}))

    return MigrateResult(
        source_path=source_path, source_kind="datax",
        output_conf=render_conf(env, source, sink),
        issues=issues, reader=rname, writer=wname,
        elapsed_ms=int((time.time() - t0) * 1000))


# ── Sqoop (import/export command lines, best effort) ──

_SQOOP_HANDLED = {
    "--connect", "--username", "--password", "--table", "--query",
    "--where", "--columns", "--target-dir", "--export-dir", "-m",
    "--num-mappers", "--split-by", "--hive-import", "--hive-table",
    "--fields-terminated-by",
}


def migrate_sqoop(text: str, source_path: str = "<inline>") -> MigrateResult:
    t0 = time.time()
    issues: list[Issue] = []
    tokens = shlex.split(text.replace("\\\n", " ").replace("\\\r\n", " "))
    if "sqoop" not in [t.lower() for t in tokens[:2]]:
        issues.append(Issue("error", "not_sqoop", {}))
        return MigrateResult(source_path=source_path, source_kind="sqoop",
                             output_conf="", issues=issues)
    mode = "import" if "import" in tokens[:3] else (
        "export" if "export" in tokens[:3] else "")
    opts: dict[str, str] = {}
    flags: set[str] = set()
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.startswith("-"):
            if tok in ("--hive-import",):
                flags.add(tok)
            elif i + 1 < len(tokens) and not tokens[i + 1].startswith("--"):
                opts[tok] = tokens[i + 1]
                i += 1
            else:
                flags.add(tok)
            if tok not in _SQOOP_HANDLED and tok.startswith("--"):
                issues.append(Issue("warn", "sqoop_flag_ignored",
                                    {"flag": tok}))
        i += 1

    url = opts.get("--connect", "")
    kind = "mysql" if url.startswith("jdbc:mysql") else (
        "postgresql" if url.startswith("jdbc:postgresql") else "mysql")
    jdbc = {
        "url": url,
        "driver": _JDBC_DRIVERS[kind],
        "user": opts.get("--username", ""),
        "password": opts.get("--password", ""),
    }
    parallel = opts.get("-m") or opts.get("--num-mappers")
    env: dict[str, Any] = {"job.mode": "BATCH"}
    if parallel:
        env["parallelism"] = int(parallel)

    if mode == "import":
        query = opts.get("--query")
        if not query:
            cols = opts.get("--columns", "*")
            query = f"select {cols} from {opts.get('--table', '')}"
            if opts.get("--where"):
                query += f" where {opts['--where']}"
        else:
            query = query.replace("$CONDITIONS", "1=1")
            issues.append(Issue("info", "sqoop_conditions", {}))
        source = ("Jdbc", {**jdbc, "query": query})
        if opts.get("--split-by"):
            source[1]["partition_column"] = opts["--split-by"]
        if "--hive-import" in flags:
            issues.append(Issue("warn", "hive_sink_todo",
                                {"table": opts.get("--hive-table", "")}))
            sink = ("Hive", {
                "table_name": opts.get("--hive-table", ""),
                "#TODO": "metastore_uri = \"thrift://<metastore>:9083\"",
            })
        else:
            sink = ("HdfsFile", {
                "path": opts.get("--target-dir", ""),
                "file_format_type": "text",
                "field_delimiter": opts.get("--fields-terminated-by", ","),
            })
    elif mode == "export":
        source = ("HdfsFile", {
            "path": opts.get("--export-dir", ""),
            "file_format_type": "text",
            "field_delimiter": opts.get("--fields-terminated-by", ","),
        })
        m = re.search(r"jdbc:\w+://[^/]+/(\w+)", url)
        sink = ("Jdbc", {**jdbc, "generate_sink_sql": True,
                         "database": m.group(1) if m else "",
                         "table": opts.get("--table", "")})
    else:
        issues.append(Issue("error", "sqoop_mode", {}))
        return MigrateResult(source_path=source_path, source_kind="sqoop",
                             output_conf="", issues=issues)

    return MigrateResult(
        source_path=source_path, source_kind="sqoop",
        output_conf=render_conf(env, source, sink),
        issues=issues, reader=f"sqoop-{mode}", writer=sink[0].lower(),
        elapsed_ms=int((time.time() - t0) * 1000))


# ── file / batch entry points ──

def migrate_text(text: str, source_path: str = "<inline>") -> MigrateResult:
    stripped = text.lstrip()
    if stripped.startswith("{"):
        return migrate_datax(text, source_path)
    if "sqoop" in stripped[:200].lower():
        return migrate_sqoop(text, source_path)
    return MigrateResult(
        source_path=source_path, source_kind="unknown", output_conf="",
        issues=[Issue("error", "unknown_format", {})])


def migrate_file(path: str | Path) -> MigrateResult:
    p = Path(path)
    return migrate_text(p.read_text(encoding="utf-8"), str(p))


@dataclass
class BatchResult:
    directory: str
    out_dir: str | None
    results: list[MigrateResult]
    elapsed_ms: int = 0

    def counts(self) -> dict[str, int]:
        return {
            "files": len(self.results),
            "ok": sum(1 for r in self.results if r.ok),
            "failed": sum(1 for r in self.results if not r.ok),
        }

    def worst_level(self) -> str | None:
        levels = {i.level for r in self.results for i in r.issues}
        for lv in LEVELS:
            if lv in levels:
                return lv
        return None

    def to_dict(self) -> dict[str, Any]:
        return {"directory": self.directory, "out_dir": self.out_dir,
                "stats": self.counts(), "elapsed_ms": self.elapsed_ms,
                "results": [r.to_dict() for r in self.results]}


def collect_jobs(directory: str | Path) -> list[Path]:
    root = Path(directory)
    out: list[Path] = []
    for pat in ("*.json", "*.sqoop", "*.sh", "*.txt"):
        out.extend(p for p in root.rglob(pat) if p.is_file())
    return sorted(set(out))


def migrate_dir(directory: str | Path,
                out_dir: str | Path | None = None) -> BatchResult:
    t0 = time.time()
    root = Path(directory)
    if not root.is_dir():
        raise ValueError(f"not a directory: {directory}")
    out_root = Path(out_dir) if out_dir else None
    results: list[MigrateResult] = []
    for p in collect_jobs(root):
        res = migrate_file(p)
        results.append(res)
        if out_root is not None and res.output_conf:
            target = (out_root / p.relative_to(root)).with_suffix(".conf")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(res.output_conf, encoding="utf-8")
    return BatchResult(directory=str(root),
                       out_dir=str(out_root) if out_root else None,
                       results=results,
                       elapsed_ms=int((time.time() - t0) * 1000))
