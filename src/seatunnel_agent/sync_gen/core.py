# -*- coding: utf-8 -*-
"""Orchestration: load schemas → filter → generate configs/DDL → manifest.

``generate_sync`` is pure apart from schema loading (no files written);
``write_outputs`` does the disk layout. The REST API calls only the
former and returns content inline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .confgen import SINK_TYPES, build_config
from .ddlgen import render_ddl
from .model import TableSpec, from_live, load_from_ddl
from .pii import PiiHit, STRATEGIES, load_rules, scan_table
from .typemap import UNMAPPED_PREFIX, map_type


@dataclass
class SyncPlan:
    source_mode: str = "ddl"             # "ddl" | "live"
    ddl_path: str | None = None
    ddl_text: str | None = None          # API 内联 DDL（优先于 ddl_path）
    database: str | None = None          # live 模式库名
    sink_type: str = "console"
    include: str | None = None           # regex vs 裸表名
    exclude: str | None = None
    pii: bool = False
    pii_rules_path: str | None = None
    pii_strategy: str = "md5"
    parallelism: int = 2


@dataclass
class TableResult:
    spec: TableSpec
    config_text: str
    ddl_text: str | None                 # console sink 不建表
    pii_hits: list[PiiHit] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def file_stem(self) -> str:
        db = self.spec.database
        return f"{db}__{self.spec.name}" if db else self.spec.name


@dataclass
class SyncResult:
    plan: SyncPlan
    tables: list[TableResult] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (table, reason)
    warnings: list[str] = field(default_factory=list)

    @property
    def unmapped_count(self) -> int:
        return sum(1 for t in self.tables for w in t.warnings
                   if UNMAPPED_PREFIX in w)

    @property
    def pii_columns(self) -> int:
        return sum(len(t.pii_hits) for t in self.tables)

    @property
    def masked_columns(self) -> int:
        return sum(1 for t in self.tables for h in t.pii_hits if h.masked)


def _validate(plan: SyncPlan) -> None:
    if plan.sink_type not in SINK_TYPES:
        raise ValueError(f"sink_type 必须是 {'/'.join(SINK_TYPES)}")
    if plan.pii_strategy not in STRATEGIES:
        raise ValueError(f"pii_strategy 必须是 {'/'.join(STRATEGIES)}")
    for pat, label in ((plan.include, "include"), (plan.exclude, "exclude")):
        if pat:
            try:
                re.compile(pat)
            except re.error as exc:
                raise ValueError(f"{label} 正则无效 {pat!r}: {exc}")


def _load_tables(plan: SyncPlan) -> tuple[list[TableSpec], list[str]]:
    if plan.source_mode == "live":
        return _load_live(plan)
    if plan.ddl_text:
        import tempfile

        # 复用文件路径的解析逻辑：内联文本落到临时文件
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td) / "inline_ddl.sql"
            tmp.write_text(plan.ddl_text, encoding="utf-8")
            return load_from_ddl(tmp)
    if not plan.ddl_path:
        raise ValueError("ddl 模式需要 ddl_path 或 ddl_text")
    return load_from_ddl(plan.ddl_path)


def _load_live(plan: SyncPlan) -> tuple[list[TableSpec], list[str]]:
    from ..text2sql.executor import config_from_env, create_executor

    cfg = config_from_env("mysql")
    if cfg is None:
        raise ValueError(
            "live 模式需要 MYSQL_HOST/MYSQL_USERNAME/MYSQL_PASSWORD 等环境变量"
            "（见 text2sql executor 文档）")
    if plan.database:
        cfg.database = plan.database
    if not cfg.database:
        raise ValueError("live 模式需要指定库名（--db 或 MYSQL_DATABASE）")
    executor = create_executor(cfg)
    schemas = executor.fetch_all_schemas()
    specs = [from_live(ts) for ts in schemas]
    warnings = []
    if specs and not any(s.primary_keys for s in specs):
        warnings.append("live 模式暂不读取主键信息，建表 DDL 退化为 DUPLICATE KEY")
    return specs, warnings


def _apply_filters(specs: list[TableSpec], plan: SyncPlan,
                   ) -> tuple[list[TableSpec], list[tuple[str, str]]]:
    inc = re.compile(plan.include) if plan.include else None
    exc = re.compile(plan.exclude) if plan.exclude else None
    kept: list[TableSpec] = []
    skipped: list[tuple[str, str]] = []
    for spec in specs:
        if inc and not inc.search(spec.name):
            skipped.append((spec.full_name, f"不匹配 include {plan.include!r}"))
            continue
        if exc and exc.search(spec.name):
            skipped.append((spec.full_name, f"匹配 exclude {plan.exclude!r}"))
            continue
        kept.append(spec)
    return kept, skipped


def generate_sync(plan: SyncPlan) -> SyncResult:
    _validate(plan)
    specs, warnings = _load_tables(plan)
    specs, skipped = _apply_filters(specs, plan)
    result = SyncResult(plan=plan, skipped=skipped, warnings=warnings)

    rules = load_rules(plan.pii_rules_path)
    for spec in sorted(specs, key=lambda s: s.full_name):
        table_warnings: list[str] = []
        hits = scan_table(spec, rules)
        if not plan.pii:
            # 不脱敏时仍然扫描：manifest 提示 + --fail-on pii 门禁
            hits = [PiiHit(h.column, h.category, h.severity,
                           h.confidence, h.evidence, masked=False)
                    for h in hits]
        for col in spec.columns:
            _, warn = map_type(col.mysql_type, _ddl_target(plan.sink_type))
            if warn:
                table_warnings.append(f"{spec.full_name}.{col.name}: {warn}")
        config_text = build_config(
            spec, plan.sink_type, hits if plan.pii else [],
            plan.pii_strategy, plan.parallelism)
        ddl_text: str | None = None
        if plan.sink_type != "console":
            ddl_text, ddl_warnings = render_ddl(spec, plan.sink_type)
            # render_ddl 重复报类型警告，去重合并
            table_warnings.extend(w for w in ddl_warnings
                                  if w not in table_warnings)
        result.tables.append(TableResult(
            spec=spec, config_text=config_text, ddl_text=ddl_text,
            pii_hits=hits, warnings=table_warnings))
    return result


def _ddl_target(sink_type: str) -> str:
    # console 不建表，类型警告扫描按 doris 口径（最严格）
    return "doris" if sink_type == "console" else sink_type


def write_outputs(result: SyncResult, out_dir: str | Path) -> list[Path]:
    """Write configs/, ddl/, manifest.json + manifest.md; returns paths."""
    import json

    from .report import render_markdown, report_to_dict

    out = Path(out_dir)
    (out / "configs").mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for t in result.tables:
        conf = out / "configs" / f"{t.file_stem}.conf"
        conf.write_text(t.config_text, encoding="utf-8")
        written.append(conf)
        if t.ddl_text:
            (out / "ddl").mkdir(exist_ok=True)
            ddl = out / "ddl" / f"{t.file_stem}.sql"
            ddl.write_text(t.ddl_text, encoding="utf-8")
            written.append(ddl)
    manifest_json = out / "manifest.json"
    manifest_json.write_text(
        json.dumps(report_to_dict(result), ensure_ascii=False, indent=2),
        encoding="utf-8")
    written.append(manifest_json)
    manifest_md = out / "manifest.md"
    manifest_md.write_text(render_markdown(result), encoding="utf-8")
    written.append(manifest_md)
    return written
