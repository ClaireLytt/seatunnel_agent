# -*- coding: utf-8 -*-
"""Render MigrateResult / BatchResult as markdown (zh/en)."""

from __future__ import annotations

from .migrator import BatchResult, Issue, MigrateResult

_MSG = {
    "zh": {
        "bad_json": "不是合法 JSON: {error}",
        "not_datax": "缺少 reader/writer,不是 DataX job 结构",
        "not_sqoop": "不是 sqoop 命令行",
        "sqoop_mode": "仅支持 sqoop import / export",
        "unknown_format": "无法识别的文件格式(既非 DataX JSON 也非 sqoop 命令)",
        "unknown_reader": "不支持的 DataX reader: {name} — 需人工编写 source",
        "unknown_writer": "不支持的 DataX writer: {name} — 需人工编写 sink",
        "multi_connection": "DataX 配了 {n} 个 connection,仅迁移第 1 个",
        "multi_table": "DataX 配了 {n} 张表,仅迁移第 1 张",
        "multi_content": "DataX 配了 {n} 个 content,仅迁移第 1 个",
        "no_database": "无法从 jdbcUrl 解析库名,请补 database: {url}",
        "write_mode": "writeMode={mode} 非 insert,请确认目标端幂等策略",
        "pre_post_sql": "{hook} 未迁移 — SeaTunnel 无对应钩子,需在调度层处理",
        "split_pk": "splitPk={col} 映射为 partition_column",
        "stream_reader": "streamreader 映射为 FakeSource(样例数据不迁移)",
        "error_limit": "errorLimit 未迁移(SeaTunnel 用检查点/重试语义): {conf}",
        "sqoop_flag_ignored": "sqoop 参数未迁移: {flag}",
        "sqoop_conditions": "$CONDITIONS 已替换为 1=1(SeaTunnel 自行分片)",
        "hive_sink_todo": "--hive-import 映射为 Hive sink,需补 metastore_uri(表 {table})",
        "title": "## DataX/Sqoop → SeaTunnel 迁移",
        "issues": "迁移说明",
        "clean": "✅ 全自动迁移,无需人工处理。",
        "stats": "文件 {files} · 成功 {ok} · 失败 {failed}",
        "disclaimer": "> 迁移结果请先用 `seatunnel-agent validate` 校验,再小流量试跑。",
    },
    "en": {
        "bad_json": "Not valid JSON: {error}",
        "not_datax": "No reader/writer — not a DataX job",
        "not_sqoop": "Not a sqoop command line",
        "sqoop_mode": "Only sqoop import / export are supported",
        "unknown_format": "Unrecognized file (neither DataX JSON nor sqoop)",
        "unknown_reader": "Unsupported DataX reader: {name} — write the source manually",
        "unknown_writer": "Unsupported DataX writer: {name} — write the sink manually",
        "multi_connection": "{n} connections configured; only the first migrated",
        "multi_table": "{n} tables configured; only the first migrated",
        "multi_content": "{n} content blocks configured; only the first migrated",
        "no_database": "Could not parse the database from jdbcUrl: {url}",
        "write_mode": "writeMode={mode} is not insert — check sink idempotency",
        "pre_post_sql": "{hook} not migrated — handle it in the scheduler",
        "split_pk": "splitPk={col} mapped to partition_column",
        "stream_reader": "streamreader mapped to FakeSource (sample data not migrated)",
        "error_limit": "errorLimit not migrated (SeaTunnel uses checkpoint/retry): {conf}",
        "sqoop_flag_ignored": "sqoop flag not migrated: {flag}",
        "sqoop_conditions": "$CONDITIONS replaced with 1=1 (SeaTunnel partitions itself)",
        "hive_sink_todo": "--hive-import mapped to a Hive sink; fill metastore_uri (table {table})",
        "title": "## DataX/Sqoop → SeaTunnel Migration",
        "issues": "Migration notes",
        "clean": "✅ Fully automatic — nothing needs a human.",
        "stats": "files {files} · ok {ok} · failed {failed}",
        "disclaimer": ("> Validate with `seatunnel-agent validate` and dry-run "
                       "on a small slice before production."),
    },
}

_MARK = {"error": "❌", "warn": "⚠️", "info": "ℹ️"}


def _lang(lang: str) -> str:
    return "en" if (lang or "").lower().startswith("en") else "zh"


def _issue_line(issue: Issue, lang: str) -> str:
    tmpl = _MSG[lang].get(issue.kind, issue.kind)
    try:
        msg = tmpl.format(**issue.params)
    except (KeyError, IndexError):
        msg = tmpl
    return f"- {_MARK.get(issue.level, '•')} [{issue.level}] {msg}"


def render_migrate_markdown(res: MigrateResult, lang: str = "zh") -> str:
    lang = _lang(lang)
    t = _MSG[lang]
    lines = [t["title"], ""]
    head = f"`{res.source_path}` ({res.source_kind}"
    if res.reader:
        head += f": {res.reader} → {res.writer}"
    lines.append(head + ")")
    lines.append("")
    if res.output_conf:
        lines.append(f"```hocon\n{res.output_conf.rstrip()}\n```")
    if res.issues:
        lines.append(f"**{t['issues']}**")
        lines.extend(_issue_line(i, lang) for i in res.issues)
    else:
        lines.append(t["clean"])
    lines += ["", t["disclaimer"]]
    return "\n".join(lines)


def render_batch_markdown(batch: BatchResult, lang: str = "zh") -> str:
    lang = _lang(lang)
    t = _MSG[lang]
    lines = [t["title"], ""]
    for r in batch.results:
        mark = "✅" if r.ok else "❌"
        lines.append(f"- {mark} `{r.source_path}` "
                     f"({r.source_kind}: {r.reader or '?'} → {r.writer or '?'})")
        lines.extend("  " + _issue_line(i, lang) for i in r.issues)
    lines += ["", "**" + t["stats"].format(**batch.counts()) + "**",
              "", t["disclaimer"]]
    return "\n".join(lines)
