# Orchestrator sample requests

Paste into `/orchestrator` or run `seatunnel-agent orchestrate "<request>"`.
Single-tool and chained examples, zh + en:

1. 审查这段 SQL 的质量问题:`SELECT * FROM dwd_order_df a, dim_user_df b WHERE a.ds='2026-10-01'`
2. 把这段 Hive SQL 翻译成 Doris,然后审查翻译结果:`SELECT city, collect_set(user_id) FROM t GROUP BY city`
3. Format this SQL and then generate test data for it:
   `select a.id,b.name from orders a join users b on a.uid=b.uid where a.ds='2026-10-01'`
4. 这个 DataX 任务迁移到 SeaTunnel,并检查生成的配置(见 datax_job.json)
5. 对比这两个版本的 SQL 会有什么上线影响:旧版 `SELECT id, amount FROM t`,新版 `SELECT id FROM t`
6. 检查 sample.sql 里有没有数据倾斜的写法(把文件内容贴进来)
7. Scan this DDL for PII columns:
   `CREATE TABLE u (phone STRING COMMENT '手机号', id_card STRING COMMENT '身份证')`
8. 这两份 DDL 之间有什么破坏性变更?旧:`CREATE TABLE t (a INT, b STRING)` 新:`CREATE TABLE t (a BIGINT)`
9. 什么是数据血缘?平台里哪个页面可以看?(不需要调用工具的问题)
