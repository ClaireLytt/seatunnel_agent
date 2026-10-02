# Prompt Lab sample prompts

Prompts that expose differences between providers/models — paste one into
the `/promptlab` page or run:

```bash
seatunnel-agent promptlab "<prompt>" -p kimi -p deepseek --parallel
```

## 1. SQL explanation (precision + hallucination test)

```
解释这条 SQL 的业务含义,并指出潜在的性能问题:
SELECT u.city, COUNT(DISTINCT o.user_id) buyers, SUM(o.amount) gmv
FROM dwd_order_df o LEFT JOIN dim_user_df u ON o.user_id = u.user_id
WHERE o.ds = '2026-10-01' GROUP BY u.city;
```

## 2. Structured output discipline (JSON only)

```
Return ONLY a JSON object (no prose, no code fence) with keys
"severity" (one of low/medium/high) and "reason" (one sentence),
assessing: a nightly ETL job's runtime grew from 10 min to 55 min
after a new LEFT JOIN was added.
```

## 3. Bilingual consistency

```
用中英双语各一句话,向业务同学解释什么是"数据倾斜"。
```
