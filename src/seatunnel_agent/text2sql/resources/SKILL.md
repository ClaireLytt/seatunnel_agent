# Text2SQL (Chat BI) Skill

## When to Trigger

Activate when the user's intent is **querying data** — asking about table
contents, metrics, counts, or any question that implies reading from a
database. Supported engines: Hive, MySQL, SQL Server, Spark SQL, Flink SQL,
ClickHouse, Doris, PostgreSQL. Typical signals: table names, Chinese
business terms matching schema comments, time range references, aggregation
words (总量/count/sum).

Do NOT activate for SeaTunnel config generation, validation, or job
management requests.

## Workflow

1. **match_tables** — Rank candidate tables by keyword/comment relevance.
2. **get_table_schema** — Fetch full column list for the top candidate(s).
3. **get_max_partition** — If the table is partitioned and the user gave no
   explicit time range, get the latest partition value.
4. **Generate SQL** — Write a safe SELECT with:
   - Partition filter (mandatory for partitioned tables).
   - Chinese column aliases from comments.
   - Aggregation / window functions if the question implies them.
   - Predicate pushdown for JOINs on partitioned tables.
5. **execute_sql** — Validate and run. The tool enforces SELECT-only,
   table whitelist, partition filter, and row LIMIT automatically.
6. **export_csv** — Export results to CSV (default: Desktop, timestamped).

## File Layout

```
text2sql/
├── agent.py            # ReAct loop, event protocol
├── schema.py           # DDL parser, SchemaStore
├── matcher.py          # Table/column fuzzy matching
├── partition.py        # Partition classification, time extraction
├── validator.py        # SQL safety (SELECT-only, whitelist, columns)
├── chart.py            # Auto-detect chart type + matplotlib figure builder
├── favorites.py        # SQL query favorites store (JSON backend)
├── i18n.py             # UI i18n dictionaries (EN/ZH)
├── exporter.py         # CSV export (UTF-8 BOM)
├── prompts.py          # System prompt assembly
├── tools.py            # Tool definitions + runtime
├── qlog.py             # Structured query logging (JSONL)
├── executor/           # Multi-engine database executors
│   ├── base.py         # Abstract base, factory, config
│   ├── hive.py         # HiveServer2 via pyhive
│   ├── mysql.py        # MySQL via pymysql
│   ├── postgres.py     # PostgreSQL via psycopg2
│   ├── sqlserver.py    # SQL Server via pymssql
│   ├── clickhouse.py   # ClickHouse via clickhouse-connect
│   ├── doris.py        # Doris/StarRocks (MySQL protocol)
│   ├── spark.py        # Spark SQL (extends Hive)
│   └── flink.py        # Flink SQL (generate-only stub)
└── resources/
    ├── SKILL.md            # This file
    ├── intent_rules.md     # Business rules (partition, aggregation, etc.)
    ├── optimize_rules.md   # Spark/Hive performance rules
    └── sidebar_fix.js      # Gradio sidebar layout fix JS
```

## Safety Invariants

- Only SELECT statements are allowed — write operations are hard-blocked.
- Only tables registered in the SchemaStore can be queried (whitelist via
  DDL file or introspected from the connected database).
- Partitioned tables (Hive/Spark) must have a partition filter — rejected otherwise.
- A row LIMIT is enforced on every query (default 1000, max 100000).
  SQL Server uses TOP N; all others use LIMIT.
- All queries are logged to `logs/text2sql_queries.jsonl`.
