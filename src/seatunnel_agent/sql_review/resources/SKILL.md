# SQL Code Review Skill

## When to Trigger

Activate when the user wants their SQL **reviewed before running it** —
pasting a SQL statement/script and asking to check, review, CR, 排错, 检查,
审查, or find problems. Supported dialects: Hive SQL, Spark SQL, Flink SQL,
MaxCompute SQL.

Do NOT activate for data querying (that is Text2SQL), SeaTunnel config
generation, or job management requests.

## What It Solves

Every SQL change otherwise needs a run-and-debug cycle to find mistakes,
which wastes time and still misses issues. This skill reviews the SQL
statically — no execution, no python scripts — and reports problems
immediately in a fixed CR-report format.

## Workflow

1. **lint_sql** — Deterministic static rules with exact line numbers
   (GROUP BY completeness, cartesian joins, `= NULL`, partition filters,
   division by zero, SELECT *, ORDER BY without LIMIT, UNION dedup,
   COUNT(DISTINCT) skew, INSERT OVERWRITE without partition, …).
   Always runs first; its findings are merged into the report automatically.
2. **get_table_schema** — Optional. When a database connection
   (e.g. `jdbc:hive2://<host>:10000`) or inline DDL was provided, verify
   column existence, JOIN key types and partition columns against the real
   schema. Without a connection the review stays purely static.
3. **Semantic review** — The LLM walks the 15-item checklist
   (see review_checklist.md): 语法正确性 / 数据质量 / SQL 性能 / 代码规范 /
   逻辑问题.
4. **submit_review** — Merges linter + LLM findings, renders the report.

## Report Format

```
## CR 报告
### 🔴 严重问题（必须修复）      | 序号 | 问题描述 | 代码位置 | 影响范围 | 修复建议 |
### 🟡 潜在风险（建议修复）      | 序号 | 问题描述 | 代码位置 | 风险说明 | 优化建议 |
### 🟢 优化建议（可选）          - bullet list
### 📊 检查统计                  检查项总数 / 通过 / 问题 / 风险
### 💡 总体评价                  one-two sentence verdict
```

## File Layout

```
sql_review/
├── agent.py       # SQLReviewAgent ReAct loop + static_review() (no-LLM mode)
├── linter.py      # Deterministic static rules (regex/scanner, line numbers)
├── report.py      # Finding model, CHECK_CATALOG (15 items), report renderer
├── prompts.py     # Dialect-aware system prompt
├── tools.py       # lint_sql / get_table_schema / submit_review
├── api.py         # REST: POST /api/sql_review/review
└── resources/     # This file + review_checklist.md
```
