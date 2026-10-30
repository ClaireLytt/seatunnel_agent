"""EN/ZH strings for migration assessment reports."""

from __future__ import annotations

from seatunnel_agent.common.utils import make_lookup

MIGRATE_I18N: dict[str, dict[str, str]] = {
    "en": {
        "rpt_title": "Pipeline Migration Assessment",
        "rpt_stats": ("jobs {jobs} · SeaTunnel {seatunnel} · Spark SQL "
                      "{spark_sql} · Flink {flink} · keep in scheduler "
                      "{scheduler} · effort S/M/L {s}/{m}/{l}"),
        "rpt_jobs": "Jobs (easiest first — migrate the quick wins early)",
        "rpt_col_job": "job",
        "rpt_col_target": "target",
        "rpt_col_effort": "effort",
        "rpt_col_why": "why",
        "rpt_col_risks": "risks",
        "target_seatunnel": "SeaTunnel",
        "target_spark_sql": "Spark SQL",
        "target_flink": "Flink",
        "target_scheduler": "keep in scheduler",
        "reason_streaming_source": "reads a streaming source",
        "reason_plain_sync": "plain table-to-table move, no transforms",
        "reason_batch_sql": "batch SQL transform",
        "reason_orchestration_only": "orchestration only, no SQL of its own",
        "risk_udf": "custom UDF / TRANSFORM — must be ported by hand",
        "risk_oracle_join": "Oracle (+) outer-join syntax — rewrite required",
        "risk_vendor_proc": "stored-procedure / cursor logic — no mechanical "
                            "translation",
        "risk_shell_logic": "shell control flow — logic must move into the "
                            "new job or the scheduler",
        "risk_dynamic_sql": "runtime-substituted SQL — verify every rendered "
                            "variant",
        "risk_local_fs": "reads/writes the local filesystem — breaks on a "
                         "cluster",
        "rpt_stubs": "SeaTunnel config skeletons for the plain syncs "
                     "(fill in credentials)",
        "rpt_order": "Migration order (producers before their consumers)",
        "rpt_shared": "Shared tables across jobs (cut over together)",
        "rpt_warnings": "Warnings",
        "rpt_disclaimer": ("> Static analysis of the scripts only — nothing "
                           "was executed. Effort is a transparent score over "
                           "statements, joins, control flow and risks; "
                           "validate each job against real data before "
                           "cutting over."),
    },
    "zh": {
        "rpt_title": "Pipeline 迁移评估",
        "rpt_stats": ("任务 {jobs} · SeaTunnel {seatunnel} · Spark SQL "
                      "{spark_sql} · Flink {flink} · 留在调度器 {scheduler} "
                      "· 工作量 S/M/L {s}/{m}/{l}"),
        "rpt_jobs": "任务清单（按难度从易到难 — 先迁快赢的）",
        "rpt_col_job": "任务",
        "rpt_col_target": "目标引擎",
        "rpt_col_effort": "工作量",
        "rpt_col_why": "依据",
        "rpt_col_risks": "风险",
        "target_seatunnel": "SeaTunnel",
        "target_spark_sql": "Spark SQL",
        "target_flink": "Flink",
        "target_scheduler": "留在调度器",
        "reason_streaming_source": "读取流式数据源",
        "reason_plain_sync": "纯表到表搬运，无变换",
        "reason_batch_sql": "批处理 SQL 变换",
        "reason_orchestration_only": "仅做编排，自身无 SQL",
        "risk_udf": "自定义 UDF / TRANSFORM — 需手工移植",
        "risk_oracle_join": "Oracle (+) 外连接语法 — 需改写",
        "risk_vendor_proc": "存储过程 / 游标逻辑 — 无法机械翻译",
        "risk_shell_logic": "shell 控制流 — 逻辑需移入新任务或调度器",
        "risk_dynamic_sql": "运行时变量拼接的 SQL — 需核对每种展开",
        "risk_local_fs": "读写本地文件系统 — 集群上会失效",
        "rpt_stubs": "纯搬运任务的 SeaTunnel 配置骨架（填上凭据即可用）",
        "rpt_order": "迁移顺序（上游生产者先迁，消费者随后）",
        "rpt_shared": "跨任务共享表（需一起切换）",
        "rpt_warnings": "警告",
        "rpt_disclaimer": ("> 仅对脚本做静态分析，未执行任何内容。工作量是"
                           "基于语句数、join 数、控制流与风险项的透明打分；"
                           "切换前请逐任务用真实数据验证。"),
    },
}


tp = make_lookup(MIGRATE_I18N)
