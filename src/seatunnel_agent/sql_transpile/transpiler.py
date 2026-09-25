"""Deterministic SQL dialect translation built on sqlglot.

Core entry points:
  translate(sql, dst, src=None)      -> TranspileResult (per-statement)
  transpile_dir(directory, dst, ...) -> BatchResult (mirrors *.sql tree)

No database connection and no LLM: the deterministic path must produce
identical output for identical input.  LLM advice lives in advisor.py and
never overwrites these results.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import sqlglot
from sqlglot import Dialect
from sqlglot.errors import ErrorLevel, ParseError

from ..sql_review.linter import split_statements
from .rules import manual_checks

# First-phase dialect matrix: sources == targets.
DIALECTS: tuple[str, ...] = ("hive", "spark", "doris", "starrocks")

_ALIASES = {
    "hiveql": "hive",
    "sparksql": "spark",
    "spark2": "spark",
    "spark3": "spark",
    "sr": "starrocks",
}

# Issue levels, most severe first (used for sorting and --fail-on).
LEVELS = ("error", "warn", "info")


def normalize_dialect(name: str) -> str:
    """Map aliases to canonical dialect names; raise on unknown ones."""
    d = _ALIASES.get(name.strip().lower(), name.strip().lower())
    if d not in DIALECTS:
        raise ValueError(
            f"unsupported dialect '{name}' (supported: {', '.join(DIALECTS)})"
        )
    return d


@dataclass
class Issue:
    """One incompatibility item. ``message``/``suggestion`` are rendered
    from ``kind`` + ``params`` by report.py so both languages stay in i18n."""

    level: str            # error | warn | info
    kind: str             # parse_error | unsupported | unknown_function | ...
    line: int             # 1-based line in the original script
    snippet: str          # short source excerpt for the report
    params: dict[str, str] = field(default_factory=dict)
    source: str = "deterministic"   # deterministic | llm

    def to_dict(self) -> dict:
        return {
            "level": self.level, "kind": self.kind, "line": self.line,
            "snippet": self.snippet, "params": dict(self.params),
            "source": self.source,
        }


@dataclass
class StatementResult:
    index: int                     # 1-based statement number
    line: int                      # 1-based start line in the script
    source_sql: str
    output_sql: str | None         # None when the statement failed to parse
    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.output_sql is not None

    @property
    def auto(self) -> bool:
        """Fully automatic: translated and nothing needs a human."""
        return self.ok and all(i.level == "info" for i in self.issues)

    def to_dict(self) -> dict:
        return {
            "index": self.index, "line": self.line,
            "source_sql": self.source_sql, "output_sql": self.output_sql,
            "ok": self.ok, "auto": self.auto,
            "issues": [i.to_dict() for i in self.issues],
        }


@dataclass
class TranspileResult:
    src_dialect: str
    dst_dialect: str
    src_inferred: bool
    statements: list[StatementResult]
    elapsed_ms: int = 0

    def counts(self) -> dict[str, int]:
        total = len(self.statements)
        failed = sum(1 for s in self.statements if not s.ok)
        auto = sum(1 for s in self.statements if s.auto)
        return {
            "total": total, "auto": auto,
            "manual": total - auto - failed, "failed": failed,
        }

    def issues(self) -> list[Issue]:
        return [i for s in self.statements for i in s.issues]

    def worst_level(self) -> str | None:
        levels = {i.level for i in self.issues()}
        for lv in LEVELS:
            if lv in levels:
                return lv
        return None

    def output_script(self, error_marker: str = "transpile-error") -> str:
        """Concatenate translated statements; failed ones keep the original
        text behind a ``-- transpile-error`` marker so nothing is lost."""
        parts: list[str] = []
        for s in self.statements:
            if s.ok:
                parts.append(s.output_sql.rstrip().rstrip(";") + ";")
            else:
                first = s.issues[0].params.get("error", "parse error") \
                    if s.issues else "parse error"
                head = f"-- {error_marker}: {first.splitlines()[0]}"
                parts.append(f"{head}\n{s.source_sql.strip()}")
        return "\n\n".join(parts) + "\n"

    def to_dict(self) -> dict:
        return {
            "src_dialect": self.src_dialect,
            "dst_dialect": self.dst_dialect,
            "src_inferred": self.src_inferred,
            "stats": self.counts(),
            "elapsed_ms": self.elapsed_ms,
            "statements": [s.to_dict() for s in self.statements],
        }


_TOKEN_REPR_RE = re.compile(r"<Token[^>]*>")


def _clean_parse_error(msg: str) -> str:
    """sqlglot embeds full Token reprs in ParseError text — too noisy for
    reports; collapse them to the token text when present."""
    return _TOKEN_REPR_RE.sub(
        lambda m: re.search(r"text: (\S+?),", m.group(0)).group(1)
        if re.search(r"text: (\S+?),", m.group(0)) else "…",
        msg,
    ).splitlines()[0]


def _snippet(sql: str, max_len: int = 60) -> str:
    one = " ".join(sql.split())
    return one if len(one) <= max_len else one[:max_len] + "…"


def infer_dialect(sql: str) -> str:
    """Best-effort source-dialect inference: the dialect that parses the
    most statements wins; ties go to the earlier entry in DIALECTS."""
    stmts = split_statements(sql)
    best, best_score = DIALECTS[0], -1
    for cand in DIALECTS:
        score = 0
        for _, stmt in stmts:
            try:
                sqlglot.parse_one(stmt, read=cand)
                score += 1
            except (ParseError, ValueError):
                continue
        if score > best_score:
            best, best_score = cand, score
        if score == len(stmts):
            break  # earlier dialect parses everything — done
    return best


def translate(
    sql: str,
    dst: str,
    src: str | None = None,
    pretty: bool = True,
) -> TranspileResult:
    """Translate a SQL script (one or more ``;``-separated statements).

    Per-statement isolation: a statement that fails to parse becomes an
    ``error``-level issue and does not affect the others.
    """
    t0 = time.time()
    dst = normalize_dialect(dst)
    inferred = src is None
    src = infer_dialect(sql) if src is None else normalize_dialect(src)

    dst_dialect = Dialect.get_or_raise(dst)
    results: list[StatementResult] = []
    for idx, (offset, stmt) in enumerate(split_statements(sql), start=1):
        stmt_line = offset + 1
        text = stmt.strip().rstrip(";")
        if not text:
            continue
        sr = StatementResult(index=idx, line=stmt_line,
                             source_sql=stmt.strip(), output_sql=None)
        try:
            ast = sqlglot.parse_one(text, read=src)
        except ParseError as e:
            err = e.errors[0] if getattr(e, "errors", None) else {}
            line = stmt_line + max(int(err.get("line", 1)) - 1, 0)
            sr.issues.append(Issue(
                level="error", kind="parse_error", line=line,
                snippet=_snippet(text),
                params={"error": _clean_parse_error(str(e))},
            ))
            results.append(sr)
            continue

        gen = dst_dialect.generator(
            unsupported_level=ErrorLevel.WARN, pretty=pretty)
        sr.output_sql = gen.generate(ast, copy=True)
        for msg in dict.fromkeys(gen.unsupported_messages):
            sr.issues.append(Issue(
                level="warn", kind="unsupported", line=stmt_line,
                snippet=_snippet(text), params={"detail": str(msg)},
            ))
        sr.issues.extend(manual_checks(ast, stmt_line, src=src, dst=dst))
        sr.issues.sort(key=lambda i: (LEVELS.index(i.level), i.line))
        results.append(sr)

    return TranspileResult(
        src_dialect=src, dst_dialect=dst, src_inferred=inferred,
        statements=results, elapsed_ms=int((time.time() - t0) * 1000),
    )


@dataclass
class FileResult:
    path: str          # source file (as given)
    rel: str           # path relative to the scanned directory
    result: TranspileResult
    out_path: str | None = None

    def to_dict(self) -> dict:
        return {"path": self.path, "rel": self.rel,
                "out_path": self.out_path, **self.result.to_dict()}


@dataclass
class BatchResult:
    directory: str
    out_dir: str | None
    src_dialect: str | None
    dst_dialect: str
    files: list[FileResult]
    elapsed_ms: int = 0

    def counts(self) -> dict[str, int]:
        agg = {"files": len(self.files), "total": 0, "auto": 0,
               "manual": 0, "failed": 0}
        for f in self.files:
            for k, v in f.result.counts().items():
                agg[k] += v
        return agg

    def worst_level(self) -> str | None:
        levels = {i.level for f in self.files for i in f.result.issues()}
        for lv in LEVELS:
            if lv in levels:
                return lv
        return None

    def to_dict(self) -> dict:
        return {
            "directory": self.directory, "out_dir": self.out_dir,
            "src_dialect": self.src_dialect, "dst_dialect": self.dst_dialect,
            "stats": self.counts(), "elapsed_ms": self.elapsed_ms,
            "files": [f.to_dict() for f in self.files],
        }


def collect_sql_files(directory: str | Path) -> list[Path]:
    root = Path(directory)
    return sorted(p for p in root.rglob("*.sql") if p.is_file())


def transpile_dir(
    directory: str | Path,
    dst: str,
    src: str | None = None,
    out_dir: str | Path | None = None,
    pretty: bool = True,
) -> BatchResult:
    """Translate every ``*.sql`` under *directory*.  With *out_dir*, write
    translated scripts to a mirrored tree (failed statements are kept as
    commented originals — see :meth:`TranspileResult.output_script`)."""
    t0 = time.time()
    root = Path(directory)
    if not root.is_dir():
        raise ValueError(f"not a directory: {directory}")
    files = collect_sql_files(root)
    out_root = Path(out_dir) if out_dir else None

    results: list[FileResult] = []
    for p in files:
        rel = p.relative_to(root)
        res = translate(p.read_text(encoding="utf-8"), dst=dst, src=src,
                        pretty=pretty)
        fr = FileResult(path=str(p), rel=str(rel), result=res)
        if out_root is not None:
            target = out_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(res.output_script(), encoding="utf-8")
            fr.out_path = str(target)
        results.append(fr)

    return BatchResult(
        directory=str(root), out_dir=str(out_root) if out_root else None,
        src_dialect=src, dst_dialect=normalize_dialect(dst), files=results,
        elapsed_ms=int((time.time() - t0) * 1000),
    )
