"""EN/ZH strings for the avro2ddl reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

AD_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Avro to DDL",
        "rpt_scope": "{flavor} → **{dialect}** · table `{table}` · "
                     "**{cols}** column(s), **{lossy}** lossy "
                     "mapping(s)",
        "rpt_columns": "Column mapping",
        "col_name": "column",
        "col_source": "schema type",
        "col_ddl": "DDL type",
        "col_note": "note",
        "note_": "-",
        "note_union_lossy": "multi-type union — landed as STRING, split "
                            "upstream if it matters",
        "note_complex_lossy": "complex type this dialect cannot hold — "
                              "landed as JSON/STRING",
        "note_unknown_lossy": "unknown schema type — landed as STRING",
        "note_enum": "enum — symbols kept in the comment",
        "rpt_ddl": "CREATE TABLE (parses clean)",
        "rpt_disclaimer": "> Generated from the schema alone — review "
                          "the Doris key/bucket stub and the lossy rows "
                          "before running. topic_schema diffs two "
                          "versions; this lands one as a table, and "
                          "seatunnel_gen turns the table into the sync "
                          "job.",
        "rpt_llm_note": "Landing review (LLM — review before DDL)",
        "ob_title": "Topic Onboarding Kit",
        "ob_scope": "table `{table}` · **{dialect}** · {source} → "
                    "{sink} · **{columns}** column(s), **{lossy}** "
                    "lossy",
        "ob_ddl": "1. CREATE TABLE (avro2ddl, parses clean)",
        "ob_conf": "2. SeaTunnel job (seatunnel_gen, linted — fill the "
                   "<...> placeholders)",
        "ob_contract": "3. Contract (contract_gen, contract_check "
                       "loads it)",
        "ob_rules": "4. DQC rules (dq_rulegen, from the sample)",
        "ob_no_sample": "> No sample rows given — pass one (CSV with "
                        "header / JSONL) and dq_rulegen drafts the "
                        "quality gates too.",
        "ob_warnings": "Warnings",
        "ob_disclaimer": "> One schema in, the landing kit out — every "
                         "piece comes from its own generator with its "
                         "round-trip guard. Review the placeholders "
                         "and lossy rows before shipping.",
    },
    "zh": {
        "rpt_title": "消息 Schema 建表",
        "rpt_scope": "{flavor} → **{dialect}** · 表 `{table}` · "
                     "**{cols}** 列,有损映射 **{lossy}** 处",
        "rpt_columns": "列映射",
        "col_name": "列",
        "col_source": "Schema 类型",
        "col_ddl": "DDL 类型",
        "col_note": "说明",
        "note_": "-",
        "note_union_lossy": "多类型 union — 落为 STRING,重要就在上游拆开",
        "note_complex_lossy": "该方言装不下的复杂类型 — 落为 JSON/STRING",
        "note_unknown_lossy": "未识别的 Schema 类型 — 落为 STRING",
        "note_enum": "枚举 — 取值集保留在注释里",
        "rpt_ddl": "CREATE TABLE（解析零错误）",
        "rpt_disclaimer": "> 仅由 Schema 生成 — Doris 的 key/分桶桩与"
                          "有损行执行前请人工复核。topic_schema 对比两版"
                          "Schema,本页把一版落成表,seatunnel_gen 再把表"
                          "变成同步作业。",
        "rpt_llm_note": "落地评审（LLM — 落 DDL 前请复核）",
        "ob_title": "Topic 接入套件",
        "ob_scope": "表 `{table}` · **{dialect}** · {source} → {sink} "
                    "· **{columns}** 列、**{lossy}** 处有损",
        "ob_ddl": "1. CREATE TABLE（avro2ddl,解析零错误）",
        "ob_conf": "2. SeaTunnel 作业（seatunnel_gen,已过 lint — 补全 "
                   "<...> 占位符）",
        "ob_contract": "3. 契约（contract_gen,contract_check 可直接"
                       "加载）",
        "ob_rules": "4. DQC 规则（dq_rulegen,按样例生成）",
        "ob_no_sample": "> 未提供样例数据 — 附一份（CSV 带表头 / "
                        "JSONL）即可同时生成 dq_rulegen 质量闸。",
        "ob_warnings": "警告",
        "ob_disclaimer": "> 一份 Schema 进,落地套件出 — 每件产物都由"
                         "原生成器产出并各自回检。占位符与有损行上线前"
                         "请人工复核。",
    },
}

tp = make_lookup(AD_I18N)
