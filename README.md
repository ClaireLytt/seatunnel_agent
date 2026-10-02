# SeaTunnel Pipeline Builder Agent

> AI-powered [Apache SeaTunnel](https://seatunnel.apache.org/) pipeline builder & data query assistant — describe your data task in natural language, and the Agent generates configs, runs jobs, diagnoses errors, and fixes them automatically. Now with **Text2SQL (Chat BI)**: ask questions in natural language and get Hive SQL results instantly.
>
> Apache SeaTunnel is an open-source, high-performance data integration engine that supports 100+ connectors (databases, message queues, file systems, data lakes, etc.).

[English](#english) | [中文](#中文)

---

<a id="english"></a>

## English

### Features

- **Natural Language → Pipeline Config**: Describe what you need ("sync MySQL users to Console"), get a working HOCON config
- **Auto-Diagnose & Fix**: When a job fails, the Agent reads the log, identifies the root cause, patches the config, and retries
- **Config Validation**: Check any `.conf` file for syntax errors and missing sections without running the job
- **Log Diagnosis**: Point the Agent at a SeaTunnel log file and get a structured root-cause analysis
- **Config Template Library**: 12 built-in templates (FakeSource, MySQL-CDC, Jdbc, Kafka, LocalFile, CSV-MySQL, StarRocks, ClickHouse, Transform) — select a template and the Agent fills in parameters
- **Connection Testing**: Test TCP connectivity to databases/services before generating configs, avoiding config-then-fail cycles
- **Connector Documentation Query**: Look up connector parameters (types, required/optional, examples) for 19 connectors before writing configs — reduces hallucination and config errors
- **Job Run Metrics**: Automatically parses SeaTunnel job output to display structured metrics (rows read/written, bytes, duration, status)
- **Config Version History**: Every `write_config` call saves a timestamped version; browse and compare past versions of any config file
- **Config Version Restore & Delete**: Restore any config to a previous version, or delete configs safely (version history preserved)
- **Config Comparison**: Compare two versions of a config with unified diff output
- **Config Explanation**: Parse a config and get a structured summary (job mode, connectors, parameters) — great for "what does this config do?"
- **Batch Task Management**: Run multiple pipeline configs sequentially with per-job results and pass/fail summary; stops on first failure by default
- **Multi-Turn Session Memory**: Agent remembers configs, job results, and connection tests across turns — say "run it again" and it knows which config
- **Config Diff Display**: When overwriting an existing config, the UI shows a unified diff of what changed
- **Task Progress Visualization**: Real-time step counter with elapsed time and streaming text output with cursor indicator
- **Token Usage Display**: Shows input/output token counts per LLM call for cost awareness
- **File Upload**: Click the `+` button next to the input box to upload `.conf` files — auto-copies to configs directory
- **Clickable Hint Cards**: Click the placeholder hints to auto-fill the input box
- **Export to ZIP**: Download a session report (Markdown) + all generated config files as a ZIP archive
- **Stop Button**: Interrupt a running agent at any time
- **Web UI**: Real-time chat interface showing the Agent's thinking, tool calls, and results — with bilingual support (English / Chinese)
- **Multi-LLM Support**: Works with Claude, GPT-4o, DeepSeek, Kimi/Moonshot, Qwen, GLM, and any OpenAI-compatible API
- **LLM Retry & Resilience**: Automatic retry with exponential backoff on rate-limit (429) and server errors (500+)
- **DeepSeek Thinking Extraction**: Shows DeepSeek-R1's chain-of-thought reasoning in the UI thinking panel
- **CLI Enhancements**: `batch` command, `--model`/`--provider` overrides, `--output` flag, `chat --resume`
- **Demo Mode**: Try the full Agent workflow without an API key
- **Text2SQL (Chat BI)**: Natural-language data querying — ask a question in Chinese or English, and the agent matches tables, generates safe Hive SQL, executes it, and exports results as CSV
- **Schema-Aware Matching**: Fuzzy table/column matching using keyword + CJK n-gram scoring against table names, column names, and Chinese comments
- **Partition Intelligence**: Automatic table suffix classification (_di/_hi/_ri = incremental, _df/_hf = full), time range extraction from natural language, and partition clause generation
- **SQL Safety Validation**: SELECT-only whitelist, forbidden keyword detection, table whitelist enforcement, LIMIT enforcement, stacked query prevention, partition filter enforcement, and column existence validation
- **CSV Export with CJK Support**: UTF-8 BOM encoding for Excel compatibility, timestamped filenames, custom output paths
- **Structured Query Logging**: JSONL-formatted logs of every query (user question, generated SQL, status, timing) for observability
- **SQL Code Review**: Static review of Hive/Spark/Flink/MaxCompute SQL — no execution needed. A deterministic linter (GROUP BY completeness, cartesian joins, `= NULL`, partition filters, division-by-zero, complexity scoring, …) plus an LLM semantic pass over a 15-item checklist, producing a fixed-format CR report (严重问题/潜在风险/优化建议/检查统计/总体评价) with table- and column-level lineage. Available as `seatunnel-agent review`, REST `POST /api/sql_review/review`, a Gradio UI page (`/sqlreview`, with history trend chart), or offline via `--static-only`. Multi-statement scripts are split and reviewed per statement with correct line numbers. Batch review a directory (`--dir`), changed files vs a git base (`--diff`), or positional paths (pre-commit style); gate CI with `--fail-on critical|risk|suggestion`; customize rules via `.sqlreview.yaml` (partition columns, disabled checks, severity overrides, custom regex rules); suppress findings inline (`-- sqlreview-disable[-next-line|-file][: category]`) or via a baseline file (`--baseline` / `--update-baseline` — only new findings fail CI); emit machine-readable output with `--format json|sarif` (SARIF uploads to GitHub Code Scanning — see `examples/ci/` and the bundled pre-commit hook in `.pre-commit-hooks.yaml`); pull live schemas with `--db host:port/database`; auto-generate fixed SQL with `--fix`; inspect review history with `review-stats`
- **Change Impact Analysis**: SQL diff × lineage — compare two SQL trees (or a git baseline) and report the release blast radius with severity levels (breaking removals / metric drift / additions); CLI `seatunnel-agent impact` with a `--fail-on` CI gate, REST `POST /api/lineage/impact`, and a Web UI at `/impact`; fully deterministic, no DB and no LLM
- **SQL Dialect Translation**: Deterministic hive/spark/doris/starrocks translation (sqlglot) with a structured incompatibility report (parse errors, unsupported syntax, unknown UDFs, storage clauses, write-side hints) — CLI `seatunnel-agent transpile`, REST `/api/transpile/`, Web UI `/transpile`; batch a directory with a mirrored output tree, gate CI with `--fail-on error|warn`, optional clearly-marked LLM advice; no DB connection, the SQL is never executed
- **PII / Sensitive Column Scan**: Naming rules × column lineage — match column names and Chinese/English comments against a sensitive-data rule catalog (phone, national ID, bank card, email, address, salary, ...), then follow column-level lineage downstream and flag **unmasked propagation** (direct copies escalate severity; `md5()`/`mask()`/`substr()` chains count as masked); custom rules via YAML — CLI `seatunnel-agent pii` with `--fail-on high|medium|low`, REST `/api/pii/`, Web UI `/pii`, demo data `examples/pii_demo/`; deterministic, no DB, no LLM
- **Batch Log Inspection**: Exception clustering over a log directory — ERROR/WARN events (with full Java stack traces) are normalized (numbers/paths/addresses/ids masked) and clustered by **root cause** (last `Caused by:` × message template × top frame), collapsing noisy logs into Top-N distinct problems with counts, affected files and first/last timestamps — CLI `seatunnel-agent loginspect` with `--fail-on error|warn`, REST `/api/loginspect/`, Web UI `/loginspect` (optional llm-generated advice), demo data `examples/logs_demo/`
- **Schema Drift Check**: Diff two DDL snapshots (files, directories or pasted scripts) and grade every structural change — breaking (removed tables/columns, incompatible type changes, partition layout changes), risk (widening types, possible renames), info (additions, comment changes) — CLI `seatunnel-agent schemadiff` with `--fail-on breaking|risk|info`, REST `/api/schemadrift/`, Web UI `/schemadrift`, demo data `examples/schema_drift_demo/`; sibling of `/impact` (SQL logic changes vs table structure changes)
- **SQL Test Data Generator**: Join-aware datasets that actually exercise a query — equi-join columns share value pools so joins match, WHERE literals are satisfied (plus one deliberate miss row), boundary rows (NULL/zero/empty) mixed in, column types from DDL or inferred from usage; optional end-to-end validation on in-memory SQLite (stdlib, zero deps) — CLI `seatunnel-agent testgen` (writes CSV + CREATE + INSERT files with `--out`), REST `/api/testgen/`, Web UI `/testgen`, demo data `examples/testgen_demo/`
- **SeaTunnel Config Deep Lint**: Param-level lint of HOCON configs against the built-in connector docs — unknown connectors/params with did-you-mean suggestions, missing required params, value-type & enum checks, source/sink role violations, CDC-vs-job.mode and parallelism sanity — CLI `seatunnel-agent conflint` with `--fail-on error|warn`, REST `/api/conflint/`, Web UI `/conflint`, demo data `examples/conflint_demo/`; parsed, never executed
- **Scheduling DAG Health Check**: Build the job DAG from SQL/SeaTunnel lineage and report what breaks a scheduler — dependency cycles, mid-layer tables nobody produces (broken upstream) or consumes (dead jobs) — plus constructive output: topological execution batches and the critical path — CLI `seatunnel-agent dagcheck` with `--fail-on error|warn`, REST `/api/dagcheck/`, Web UI `/dagcheck`, demo data `examples/dagcheck_demo/`
- **Metric Consistency Check**: Same-named output columns defined differently across jobs (the top reason two reports disagree) — expressions canonicalized before comparing (aliases/qualifiers stripped, COUNT(1)≡COUNT(*)): different formulas = high, copies from different source columns = medium — CLI `seatunnel-agent metricdiff` with `--fail-on high|medium`, REST `/api/metricdiff/`, Web UI `/metricdiff`, demo data `examples/metricdiff_demo/`
- **SQL Formatter**: Deterministic sqlglot pretty-print with a black-style workflow — `--fail-on change` as the CI check, `--write` to apply, statements that do not parse are kept verbatim so formatting never destroys content; bare `SELECT *` flagged — CLI `seatunnel-agent sqlfmt`, REST `/api/sqlfmt/`, Web UI `/sqlfmt`, demo data `examples/sqlfmt_demo/`
- **Three-workspace hub**: the landing page splits the platform into **Data Agents** (`/data` — the agents above, grouped with an instant filter), an **AI Platform** (`/ai`) and a **DevOps workspace** (`/devops`), with the cross-cutting engineering tools (log inspection, UI testing, MCP toolbox, settings) right on the landing page:
- **Agent Orchestrator** *(AI Platform)*: one chat entry for the whole platform — the LLM routes a natural-language request to the right deterministic agents (review, transpile, impact, migrate, skew, fmt, lint, drift, PII, testgen) and chains steps in a bounded tool-use loop with per-tool error isolation; without an API key it degrades to keyword suggestions (suggest-only) — CLI `seatunnel-agent orchestrate`, REST `/api/orchestrator/`, chat Web UI `/orchestrator` with collapsible tool steps, samples `examples/orchestrator_demo/`
- **LLM Eval** *(AI Platform)*: golden YAML suites for the LLM features (text2sql, sql_review, raw prompts) — deterministic checkers (`contains`/`regex`/`equals`/`sql_valid`/`json_valid`) score every case, run history powers `--fail-on regression` (pass→fail flips or score drop >0.01), and the optional LLM judge stays advisory — CLI `seatunnel-agent llmeval`, REST `/api/llmeval/`, Web UI `/llmeval` with a score trend chart, demo suites `examples/llmeval_demo/`
- **Prompt Lab** *(AI Platform)*: run one prompt across several provider profiles side-by-side (outputs, tokens, latency, unified diff) — each profile becomes a private Settings, never switching the app's active provider, and profile secrets never leave the process — CLI `seatunnel-agent promptlab`, REST `/api/promptlab/`, Web UI `/promptlab`, sample prompts `examples/promptlab_demo/`
- **LLM Cost Observability** *(AI Platform)*: price the cross-agent LLM usage log against an approximate, YAML-overridable catalog (longest-prefix match) — per-model/day/agent roll-ups, trailing-mean anomaly flags, and a `--fail-on budget` CI gate — CLI `seatunnel-agent llmcost`, REST `/api/llmcost/`, Web UI `/llmcost` with stacked cost charts, demo data `examples/llmcost_demo/`
- **Secret Scan** *(DevOps)*: leaked-credential scanner — provider tokens (AWS/GitHub/GitLab/Slack/Aliyun), private keys, password/API-key assignments, DSN-embedded passwords and a Shannon-entropy fallback; placeholders filtered, previews always masked, suppression via a line pragma or `.secretscan.yaml` — CLI `seatunnel-agent secretscan --fail-on high|medium|low`, REST `/api/secretscan/`, Web UI `/secretscan`, demo `examples/secretscan_demo/`
- **CI Log Triage** *(DevOps)*: cluster failed-job logs into Top-N root causes (numbers/paths/hashes masked before grouping), plus flaky detection (same commit both passed and failed) and duration drift from runs metadata; `--gh owner/repo` pulls recent runs via the gh CLI — CLI `seatunnel-agent ciinspect --fail-on flaky`, REST `/api/ciinspect/`, Web UI `/ciinspect`, demo `examples/ciinspect_demo/`
- **Dependency Health** *(DevOps)*: offline check of pyproject/requirements — declared-but-missing or spec-violated installs (high), unpinned/conflicting declarations and copyleft licenses (medium), unknown licenses (info), with a full inventory table — CLI `seatunnel-agent depcheck --fail-on high|medium`, REST `/api/depcheck/`, Web UI `/depcheck`, demo `examples/depcheck_demo/`
- **Release Notes** *(DevOps)*: conventional-commit changelog grouped by type with breaking-change section and a semver bump suggestion (breaking→major, feat→minor, else patch); optional advisory LLM polish — CLI `seatunnel-agent relnotes` (`--log-file` for offline input), REST `/api/release/`, Web UI `/release`, demo `examples/release_demo/`

### Quick Start

#### Prerequisites

- Python 3.10+
- An LLM API key (Anthropic / OpenAI / DeepSeek / Kimi / Qwen / GLM — any one)
- Apache SeaTunnel (optional — config generation, validation, and diagnosis work without it)

#### Step 1: Clone & Install

```bash
git clone https://github.com/ClaireLytt/seatunnel_agent.git
cd seatunnel_agent

# Install with Web UI + all LLM providers
pip install -e ".[all,ui]"
```

<details>
<summary>Other install options</summary>

```bash
# CLI only (no UI)
pip install -e .

# With specific LLM provider
pip install -e ".[ui]"
pip install anthropic    # for Claude
pip install openai       # for DeepSeek/Kimi/Qwen/GPT

# Development (includes test dependencies)
pip install -e ".[dev]"
```

</details>

#### Step 2: Configure `.env`

> 💡 **No-file alternative:** launch the web UI and open the **Settings** page (`/settings`) —
> provider, API key, model and base URL can all be entered in the browser (key encrypted at
> rest under `~/.seatunnel-agent/`), take effect immediately, and override `.env` for the
> web UI until you click *Restore .env*. The page also offers named **profiles** (one per
> provider, one-click switch), **database connection** management (shared with the Data
> Comparison presets), a real **connection test**, and a 30-day **LLM token usage** summary
> (also via `seatunnel-agent settings --usage`). The `.env` file is still required for CLI runs.

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
# Required: your LLM API key
API_KEY=sk-your-api-key-here

# LLM provider: "anthropic" or "openai" (for all OpenAI-compatible APIs)
LLM_PROVIDER=anthropic

# Model name (default: claude-opus-5)
MODEL_NAME=claude-opus-5

# For non-default API endpoints (DeepSeek, Kimi, Qwen, etc.)
# LLM_BASE_URL=https://api.deepseek.com

# Path to your SeaTunnel installation (optional)
# SEATUNNEL_HOME=/opt/apache-seatunnel

# Max retry attempts for failed jobs (default: 3)
# MAX_RETRIES=3

# Job execution timeout in seconds (default: 120)
# JOB_TIMEOUT=120

# LLM temperature (default: 0.0 for deterministic output)
# TEMPERATURE=0.0

# Directory for generated configs (default: configs)
# CONFIG_DIR=configs
```

<details>
<summary>Configuration examples for different LLM providers</summary>

**DeepSeek**
```env
LLM_PROVIDER=openai
API_KEY=sk-your-deepseek-key
MODEL_NAME=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
```

**Kimi / Moonshot**
```env
LLM_PROVIDER=openai
API_KEY=sk-your-kimi-key
MODEL_NAME=kimi-k2.7-code
LLM_BASE_URL=https://api.moonshot.cn/v1
```

**Qwen (通义千问)**
```env
LLM_PROVIDER=openai
API_KEY=sk-your-qwen-key
MODEL_NAME=qwen-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

**GLM (智谱)**
```env
LLM_PROVIDER=openai
API_KEY=your-glm-key
MODEL_NAME=glm-4
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
```

**OpenAI**
```env
LLM_PROVIDER=openai
API_KEY=sk-your-openai-key
MODEL_NAME=gpt-4o
```

</details>

#### Step 3: Launch

```bash
# Start the Web UI (opens browser automatically)
seatunnel-agent ui

# Or use the CLI
seatunnel-agent run --task "Generate 10 fake rows to console"
```

#### Step 4 (Optional): Configure Text2SQL (Chat BI)

Text2SQL supports 8 database engines. Install the driver for your database:

```bash
pip install -e ".[mysql]"       # MySQL / Doris
pip install -e ".[postgres]"    # PostgreSQL
pip install -e ".[hive]"        # Hive / Spark SQL
pip install -e ".[sqlserver]"   # SQL Server
pip install -e ".[clickhouse]"  # ClickHouse
pip install -e ".[db-all]"      # All database drivers
pip install -e ".[chart]"       # Chart visualization (matplotlib)
```

Add your database connection to `.env` (example for MySQL):

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=mydb
MYSQL_USERNAME=readonly_user
MYSQL_PASSWORD=secret
```

See `.env.example` for all supported engines (Hive, Spark SQL, MySQL, SQL Server, ClickHouse, Doris, PostgreSQL). A read-only database account is recommended.

Optionally, create a `config/schema_ddl.sql` whitelist with CREATE TABLE DDLs to restrict which tables the agent can query. Without it, all tables in the connected database are available.

### Docker Deployment

Run with Docker (no Python installation needed):

```bash
# 1. Configure your .env
cp .env.example .env
# Edit .env with your API key

# 2. Build and run
docker compose up --build

# Opens at http://localhost:7860
```

Or build manually:

```bash
docker build -t seatunnel-agent .
docker run -p 7860:7860 --env-file .env seatunnel-agent
```

### Web UI Guide

Launch the Web UI:

```bash
seatunnel-agent ui
# Opens http://127.0.0.1:7860 in your browser

# Allow LAN access
seatunnel-agent ui --host 0.0.0.0
```

#### Interface Overview

```
┌──────────────┬─────────────────────────────────────────┐
│   Sidebar    │                              [Lang: EN] │
│              │                                         │
│ [+ New Chat] │     ┌──────────────────────────┐        │
│              │     │         ST logo           │        │
│  History ▼   │     │  How can I help you       │        │
│  ├─ Chat 1   │     │  build a pipeline?        │        │
│  └─ Chat 2   │     │                           │        │
│              │     │  [hint 1] [hint 2] [hint3]│        │
│  Template ▼  │     │       📖 Docs             │        │
│  MODE  ▼     │     └──────────────────────────┘        │
│  CONFIG PATH │                                         │
│  [Connect]   │  ┌──────────────────────────────────┐   │
│  STATUS      │  │ [+] [Message input] [Demo] [■] [➤]│   │
│  [Export]    │  └──────────────────────────────────┘   │
└──────────────┴─────────────────────────────────────────┘
```

#### Step-by-Step Usage

1. **Connect to LLM**: Click the **Connect** button in the sidebar. If your `.env` is configured correctly, the status shows `✅ Connected, Model: xxx`

2. **Choose a Mode**:
   | Mode | What it does |
   |------|-------------|
   | Natural Language | Describe a task in plain text → Agent generates and runs a config |
   | Run Config | Point to an existing `.conf` file → Agent runs it and fixes errors |
   | Validate Config | Check a config file for syntax/structure issues without running |
   | Diagnose Log | Analyze a SeaTunnel log file to find the root cause of errors |

3. **Send a message**: Type your request in the input box and click **Send** (or press Enter)

4. **Watch the Agent work**: The chat shows the Agent's reasoning process in real time:
   - 💭 **Thinking** — the Agent's internal reasoning
   - 🔧 **Tool Call** — which tool is being called and with what arguments
   - ✅/❌ **Result** — the tool's output (success/failure)
   - Final answer with the generated config or diagnosis

5. **Try Demo Mode**: Click the **Demo** button to see the full workflow without needing an API key. This runs a simulated agent flow using local tools.

6. **Manage Conversations**:
   - **+ New Chat**: Start a fresh conversation
   - **History**: Click a previous conversation to reload it
   - **Rename / Delete**: Select a conversation, then use the Rename or Delete buttons that appear

7. **Switch Language**: Use the language dropdown in the top-right corner to switch between English and Chinese

#### Sharing with Others

Generate a temporary public URL (valid for 72 hours):

```bash
seatunnel-agent ui --share
```

This creates a `https://xxxxx.gradio.live` link that anyone can access. Your computer must stay on and the process running.

Custom port:

```bash
seatunnel-agent ui --port 8080
```

### CLI Usage

```bash
# Natural language task
seatunnel-agent run --task "Generate 10 fake rows with id, name, age and print to console"

# Run an existing config (auto-fix on failure)
seatunnel-agent run --config examples/fake_to_console.conf

# Save output to file
seatunnel-agent run --task "..." --output result.txt

# Validate a config file
seatunnel-agent validate --config examples/fake_to_console.conf

# Diagnose a log file
seatunnel-agent diagnose --log /path/to/seatunnel.log

# Batch run multiple configs
seatunnel-agent batch -c config1.conf -c config2.conf --stop-on-failure

# Interactive chat (with session resume)
seatunnel-agent chat
seatunnel-agent chat --list-sessions          # list saved sessions
seatunnel-agent chat --resume <session_id>    # resume a specific session

# Override model/provider at runtime
seatunnel-agent --model deepseek-chat --provider openai run --task "..."

# Verbose output
seatunnel-agent -v run --task "..."
```

### Text2SQL (Chat BI) Usage

The Text2SQL feature lets you query Hive tables using natural language. Access it from the Web UI's **Text2SQL** page or programmatically.

#### How It Works

```
User Question (Natural Language)
    │
    ▼
┌─────────────────────────────────────────┐
│          Text2SQL Agent (ReAct)          │
│                                         │
│  1. match_tables    → rank candidates   │
│  2. get_table_schema → inspect columns  │
│  3. get_max_partition → latest partition │
│  4. Generate SQL    → LLM + rules       │
│  5. execute_sql     → validate & run    │
│  6. export_csv      → download results  │
└─────────────────────────────────────────┘
    │
    ▼
Hive SQL Results + CSV Export
```

#### Example Queries

| Question | Generated SQL (simplified) |
|----------|---------------------------|
| "查询最近7天的入库单量" | `SELECT COUNT(*) FROM zz.dwm_scm_detail_di WHERE pt >= '20260907' AND pt <= '20260914'` |
| "各品牌的入库总量" | `SELECT brand_name, SUM(inbound_cnt) FROM ... WHERE pt = '<max>' GROUP BY brand_name` |
| "查询学生表所有数据" | `SELECT * FROM atest.student LIMIT 1000` |

#### Safety Guarantees

- **SELECT-only**: Write operations (INSERT/UPDATE/DELETE/DROP/ALTER) are hard-blocked
- **Table whitelist**: Only tables in `config/schema_ddl.sql` can be queried
- **Partition enforcement**: Partitioned tables must have a partition filter — queries without one are rejected
- **Row LIMIT**: Every query gets a LIMIT (default 1000, max 100,000)
- **Query logging**: All queries are logged to `logs/text2sql_queries.jsonl`

### Supported LLMs

| Provider | Example Models | Config |
|----------|---------------|--------|
| Anthropic (Claude) | claude-opus-5, claude-sonnet-5 | `LLM_PROVIDER=anthropic` |
| OpenAI | gpt-4o, gpt-4o-mini | `LLM_PROVIDER=openai` |
| DeepSeek | deepseek-chat, deepseek-reasoner | `LLM_PROVIDER=openai` + `LLM_BASE_URL=https://api.deepseek.com` |
| Kimi/Moonshot | kimi-k2.7-code | `LLM_PROVIDER=openai` + `LLM_BASE_URL=https://api.moonshot.cn/v1` |
| Qwen | qwen-plus, qwen-turbo | `LLM_PROVIDER=openai` + `LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1` |
| GLM (Zhipu) | glm-4 | `LLM_PROVIDER=openai` + `LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4` |

Any OpenAI-compatible API works — just set `LLM_PROVIDER=openai` and the correct `LLM_BASE_URL`.

### Architecture

```
User Input (Natural Language)
    │
    ├───────────────────────┐
    ▼                       ▼
┌──────────────────┐  ┌──────────────────────┐
│  SeaTunnel Agent │  │  Text2SQL Agent      │
│  (Pipeline)      │  │  (Chat BI)           │
│                  │  │                      │
│  ┌────────────┐  │  │  ┌────────────────┐  │
│  │  LLM +     │  │  │  │ LLM + Schema   │  │
│  │  ReAct     │  │  │  │ Store + ReAct  │  │
│  │  Loop      │  │  │  │ Loop           │  │
│  └─────┬──────┘  │  │  └──────┬─────────┘  │
│        │         │  │         │             │
│  ┌─────▼──────┐  │  │  ┌──────▼─────────┐  │
│  │ 16 Tools   │  │  │  │  5 Tools       │  │
│  │ run_job    │  │  │  │ match_tables   │  │
│  │ read/write │  │  │  │ get_schema     │  │
│  │ validate   │  │  │  │ get_partition  │  │
│  │ diagnose   │  │  │  │ execute_sql    │  │
│  │ templates  │  │  │  │ export_csv     │  │
│  │ ...        │  │  │  └────────────────┘  │
│  └────────────┘  │  │                      │
└────────┬─────────┘  └──────────┬───────────┘
         │                       │
         ▼                       ▼
  Apache SeaTunnel        HiveServer2
  (Data Integration)      (Data Query)
```

### Project Structure

```
seatunnel_agent/
├── pyproject.toml              # Project config & dependencies
├── .env.example                # Environment variable template
├── Dockerfile                  # Docker image build
├── docker-compose.yml          # Docker Compose with persistent volumes
├── config/
│   └── schema_ddl.sql          # Text2SQL table whitelist (Hive CREATE TABLE DDLs)
├── src/seatunnel_agent/
│   ├── config.py               # Config loading (.env → Settings)
│   ├── llm.py                  # Multi-provider LLM abstraction
│   ├── utils.py                # Utility functions
│   ├── tools.py                # 16 tool definitions + executor (SeaTunnel pipeline)
│   ├── templates.py            # 12 built-in pipeline config templates
│   ├── connector_docs.py       # Connector parameter documentation (19 connectors)
│   ├── prompts.py              # System prompt (SeaTunnel pipeline agent)
│   ├── agent.py                # ReAct loop + session context tracking
│   ├── history.py              # Chat session persistence
│   ├── cli.py                  # Click CLI entry point
│   ├── ui.py                   # Gradio Web UI hub (multipage app)
│   ├── text2sql_ui.py          # Gradio Text2SQL page (streaming chat)
│   └── text2sql/               # Text2SQL (Chat BI) agent package
│       ├── __init__.py         # Package exports
│       ├── schema.py           # DDL parser, SchemaStore, table/column models
│       ├── matcher.py          # Table/column fuzzy matching (keyword + CJK n-gram)
│       ├── partition.py        # Partition classification, time range extraction
│       ├── validator.py        # SQL safety (SELECT-only, whitelist, columns, LIMIT)
│       ├── chart.py            # Auto-detect chart type + matplotlib rendering
│       ├── favorites.py        # SQL query favorites store (JSON backend)
│       ├── i18n.py             # UI i18n dictionaries (EN/ZH)
│       ├── exporter.py         # CSV export (UTF-8 BOM for Excel)
│       ├── prompts.py          # System prompt assembly (rules + schema)
│       ├── tools.py            # 5 tool definitions + runtime + partition enforcement
│       ├── agent.py            # ReAct loop, event protocol, multi-turn
│       ├── qlog.py             # Structured query logging (JSONL)
│       ├── executor/           # Multi-engine database executors
│       │   ├── base.py         # Abstract base, factory, DatabaseConfig
│       │   ├── hive.py         # HiveServer2 via pyhive
│       │   ├── mysql.py        # MySQL via pymysql
│       │   ├── postgres.py     # PostgreSQL via psycopg2
│       │   ├── sqlserver.py    # SQL Server via pymssql
│       │   ├── clickhouse.py   # ClickHouse via clickhouse-connect
│       │   ├── doris.py        # Doris/StarRocks (MySQL protocol)
│       │   ├── spark.py        # Spark SQL (extends Hive)
│       │   └── flink.py        # Flink SQL (generate-only)
│       └── resources/
│           ├── SKILL.md        # Skill entry point (when to trigger, workflow)
│           ├── intent_rules.md # Business rules (partition, aggregation, etc.)
│           └── optimize_rules.md # Spark/Hive performance optimization rules
├── scripts/                    # Dev workflow scripts
│   ├── ship.ps1                # Commit & push to current branch
│   └── next.ps1                # Sync main, create new branch
├── docs/
│   └── text2sql_test_doc.md    # Text2SQL test document (62 automated + manual cases)
├── tests/                      # 369 unit tests
│   ├── test_config.py          # Settings & env loading
│   ├── test_tools.py           # All 16 tools, path guards, version collision, metrics
│   ├── test_templates.py       # Template registry, rendering, tool integration
│   ├── test_connector_docs.py  # Connector documentation query & lookup
│   ├── test_agent.py           # ReAct loop, context tracking, entry points
│   ├── test_history.py         # Session persistence, session_id sanitization
│   ├── test_llm.py             # LLM client, retry logic, token usage, DeepSeek thinking
│   ├── test_prompts.py         # System prompt, task hints, tool references
│   ├── test_ui_format.py       # Event formatting, export, normalize, EventCollector
│   ├── test_utils.py           # Utility functions (truncate, log resolution)
│   ├── test_cli.py             # CLI commands, batch, --list-sessions
│   └── test_text2sql.py        # Text2SQL: schema, validation, matching, partition, tools (62 tests)
└── examples/                   # Example configs
    ├── fake_to_console.conf
    └── mysql_to_console.conf
```

### Testing

```bash
# Run all 369 tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_agent.py -v

# Run Text2SQL tests only
pytest tests/test_text2sql.py -v

# Run with coverage
pytest tests/ --cov=seatunnel_agent --cov-report=term-missing
```

Test coverage by module:

| Module | Tests | Coverage |
|--------|-------|----------|
| `config.py` | 14 | Settings loading, env vars (JOB_TIMEOUT, TEMPERATURE, CONFIG_DIR, MAX_TOKENS), provider validation |
| `tools.py` | 67 | All 16 tools, path traversal guards, extension validation, version collision fix, diff, metrics, batch, restore, delete, compare, explain |
| `templates.py` | 25 | 12 templates: registry, rendering, categories, parameter validation, tool integration |
| `connector_docs.py` | 25 | 19 connectors: query, param detail, case-insensitive lookup, type validation |
| `agent.py` | 28 | ReAct loop, context tracking (all 16 tools), retry limit break, entry points |
| `history.py` | 29 | Save/load, rename, delete, session_id sanitization, agent context roundtrip, path migration |
| `llm.py` | 31 | Anthropic & OpenAI clients, retry logic (string code handling), token usage, DeepSeek thinking |
| `prompts.py` | 13 | System prompt content, task hints, tool references |
| `ui.py` | 49 | Event formatting, export, elapsed time, token usage display, tool emojis, EventCollector |
| `utils.py` | 17 | truncate, find_latest_log, safe_json, resolve_log_path |
| `cli.py` | 9 | CLI commands, batch, --list-sessions, help text |
| `text2sql/` | 62 | Schema parsing, SQL validation (SELECT-only, whitelist, stacked queries), table/column matching, partition rules, CSV export, query logging, column validation, partition enforcement, tool layer, edge cases |

Full Text2SQL test documentation: [`docs/text2sql_test_doc.md`](docs/text2sql_test_doc.md)

### Data Lineage Agent

Full-chain table & column lineage built from SQL files, SeaTunnel configs
and/or the Hive metadata lineage table — upstream/downstream chains,
column-level impact, SLA analysis, governance health check, snapshots and
OpenLineage export. Web UI at `/lineage`, plus:

```bash
seatunnel-agent lineage --sql-dir examples/lineage_demo -t dws.gmv_daily            # chain report
seatunnel-agent lineage --sql-dir sql/ -t dwd.orders_di -c amount                   # column impact
seatunnel-agent lineage --sql-dir sql/ --check                                      # health check
seatunnel-agent lineage --sql-dir sql/ --ask "改 orders 的 amount 影响哪些下游?"     # agent mode
seatunnel-agent lineage-mcp --sql-dir sql/                                          # MCP server (stdio)
```

### Data Dictionary Generator

Markdown data dictionary straight from the lineage graph — per table:
layer, upstream/downstream, every column with its sources and expression
(aggregations flagged). Deterministic; `--describe` optionally adds
one-line LLM table descriptions, clearly marked `llm-generated`:

```bash
seatunnel-agent datadict -d examples/lineage_demo -o dict.md
seatunnel-agent datadict -d sql/ --lang en --describe
```

### Change Impact Analysis Agent

SQL diff × lineage downstream walk: compare two SQL trees (two directories,
the working tree vs a git ref, or just two pasted SQL snippets — optionally with a context SQL tree so a snippet's blast radius covers the repo's real consumers) and report the release blast radius —
which target tables changed (added / removed / column-expression drift),
which downstream tables are affected and how deep, with a severity model
(`error` = breaking removal, `warn` = metric drift with consumers, `info` =
additions) that gates CI via `--fail-on`. Fully deterministic — no database,
no LLM. Web UI at `/impact`, REST
`POST /api/lineage/impact`, an MCP tool (`lineage_change_impact` on the
`lineage-mcp` server), CI gate templates in `examples/ci/*impact*`, demo
data in `examples/impact_demo/`:

```bash
seatunnel-agent impact --old-dir examples/impact_demo/old --sql-dir examples/impact_demo/new
seatunnel-agent impact --base origin/main --sql-dir sql/                # git baseline mode
seatunnel-agent impact --old-dir old/ --sql-dir new/ -F json --fail-on error   # CI gate
seatunnel-agent impact --base origin/main --sql-dir sql/ -F md-comment          # compact PR-comment markdown
seatunnel-agent impact-stats                                                    # analysis history & hot tables
```

### DataX/Sqoop Migration Agent

Rule-based, deterministic conversion of DataX job JSON and sqoop
import/export command lines into SeaTunnel configs — jdbc readers/writers
(query building from column/where, splitPk → partition_column,
speed.channel → parallelism), doris/starrocks/hdfs/local-file/stream
plugins, with every unmappable knob surfaced as a migration note (never
silently dropped; unknown plugins produce an error + TODO block). Web UI
at `/migrate`, demo data in `examples/migrate_demo/`:

```bash
seatunnel-agent migrate examples/migrate_demo/01_mysql_to_doris.json -o job.conf
seatunnel-agent migrate -D datax_jobs/ -o seatunnel_confs/           # batch, mirrored tree
seatunnel-agent migrate -D datax_jobs/ -F json --fail-on error       # CI gate
```

### SQL Dialect Translation Agent

Deterministic SQL translation between hive / spark / doris / starrocks / mysql / presto(trino) / clickhouse
(sqlglot-based — same output for the same input, works with `--no-llm` and
no API key), plus a structured incompatibility report: parse errors,
target-dialect unsupported syntax, unknown UDFs, storage clauses
(`STORED AS` / `TBLPROPERTIES`), write-side hints (`DISTRIBUTE BY`), and
`INSERT ... PARTITION` notes. Optional LLM advice for the flagged items is
rendered separately and clearly marked `llm-generated` — it never
overwrites the deterministic output. No database connection, the SQL is
never executed. Web UI at `/transpile`, REST under `/api/transpile/`, demo
data in `examples/transpile_demo/`:

```bash
seatunnel-agent transpile --from hive --to doris query.sql                          # single file
seatunnel-agent transpile --to starrocks -s "SELECT get_json_object(p,'$.a') FROM t" # inline (source inferred)
seatunnel-agent transpile --from hive --to doris -D sql/ -o doris_sql/              # batch, mirrored tree
seatunnel-agent transpile --to doris -D sql/ -F json --no-llm --fail-on error       # CI gate
```

### Data Skew Analyzer Agent

Detects skew-prone SQL patterns with 13 static rules (COUNT(DISTINCT)
single-point aggregation, NULL-heavy join keys, functions on join keys,
global ORDER BY / DISTINCT / UNION dedup, dynamic-partition writes without
DISTRIBUTE BY, missing broadcast hints, ...) and rewrites the SQL with the
LLM (salting, two-stage aggregation, skew-join hints). Supports Spark SQL /
MaxCompute SQL (Hive accepted as compatible input). Optionally connect a
datasource to **verify** the skew with live key-distribution probes
(parallel, sampled via TABLESAMPLE where supported, hot values fed back
into the rewrite prompt and engine-parameter hints) and to **measure
consistency** between the original and optimized SQL (row diff for small
results, per-column aggregate fingerprints for large ones). Confirmed skew
also yields deterministic rewrite templates with the measured values filled
in. Web UI at `/dataskew` (analysis history, SQL file upload, saved
connections shared with Settings, one-click bridge from the SQL Review
page), REST under `/api/skew/`; static scan is deterministic — no API key,
nothing executed:

```bash
seatunnel-agent skew -s "SELECT count(distinct uid) FROM t"          # inline, static
seatunnel-agent skew -f etl.sql --dialect maxcompute --lang en       # single file
seatunnel-agent skew -D sql/ --fail-on high                          # CI gate over a directory
seatunnel-agent skew -f etl.sql --llm -o report.md                   # + LLM rewrite
seatunnel-agent skew-stats                                           # history & aggregates
seatunnel-agent skew-mcp                                             # MCP server (stdio)
```

### PII / Sensitive Column Scan Agent

Naming rules × column lineage: a built-in rule catalog (phone, national ID,
bank card, email, person name, address, salary, birthday, license plate,
IP, ...) matches column names **and comments** (Chinese keywords included)
from `CREATE TABLE` statements and lineage column edges. Every hit is then
pushed through column-level lineage: the report shows where the value
spreads downstream and whether each propagation edge is masked
(`md5`/`sha2`/`mask`/`substr`/... count as masked, direct copies do not) —
an unmasked spread escalates the severity one level. Already-hashed columns
(`phone_md5`) are demoted to low. Custom rules append via YAML. Web UI at
`/pii`, REST under `/api/pii/` (directory-whitelisted via
`PII_API_ALLOWED_DIRS`), demo data `examples/pii_demo/`; fully
deterministic — no DB, no LLM:

```bash
seatunnel-agent pii --dir warehouse_sql/                             # scan a directory
seatunnel-agent pii --sql "CREATE TABLE t (phone STRING COMMENT '手机号');"
seatunnel-agent pii --dir sql/ --rules my_rules.yaml --lang en       # custom rules
seatunnel-agent pii --dir sql/ -F json --fail-on high                # CI gate
```

### Batch Log Inspection Agent

Exception clustering over a log directory: ERROR/WARN lines and full Java
stack traces become events, volatile tokens (numbers, paths, addresses,
ids) are masked, and events cluster by **root cause** — the last
`Caused by:` exception × message template × top stack frame — so the same
failure from different jobs/files lands in one cluster with counts, first/
last timestamps and a representative sample. Web UI at `/loginspect` (with
optional `llm-generated` root-cause advice), REST under `/api/loginspect/`
(whitelisted via `LOGINSPECT_API_ALLOWED_DIRS`), demo data
`examples/logs_demo/`:

```bash
seatunnel-agent loginspect --dir logs/                               # cluster a directory
seatunnel-agent loginspect --dir logs/ --no-warn --top 5             # errors only, top 5
seatunnel-agent loginspect -f seatunnel.log --lang en                # single file
seatunnel-agent loginspect --dir logs/ -F json --fail-on error       # CI gate
```

### Schema Drift Check Agent

Diff two schema snapshots (CREATE TABLE scripts — files, directories or
pasted DDL) and grade every change: **breaking** (removed tables/columns,
incompatible type changes, partition layout changes), **risk** (widening
type changes like INT→BIGINT / DECIMAL(10,2)→DECIMAL(16,2), possible
renames — same type and comment), **info** (added tables/columns, comment
changes). Sibling of the Change Impact agent: `/impact` covers SQL logic
changes, this covers table structure. Web UI at `/schemadrift`, REST under
`/api/schemadrift/` (whitelisted via `SCHEMADRIFT_API_ALLOWED_DIRS`), demo
data `examples/schema_drift_demo/`:

```bash
seatunnel-agent schemadiff --old ddl_v1/ --new ddl_v2/               # two directories
seatunnel-agent schemadiff --old old.sql --new new.sql --lang en     # two files
seatunnel-agent schemadiff --old v1/ --new v2/ -F json --fail-on breaking  # CI gate
```

### SQL Test Data Generator Agent

Generates minimal per-table datasets that actually exercise a query:
equi-join columns share one value pool (joins are guaranteed to match,
including through single-source CTEs), WHERE literals (`dt = '...'`,
`status IN (...)`, BETWEEN) are satisfied by most rows — plus one
deliberate miss row so filters are provably selective — and boundary rows
(NULL / zero / empty string) are mixed in. Column types come from the
optional DDL, otherwise inferred from literals, usage and naming. The
generated data + query can be validated end-to-end on in-memory SQLite
(stdlib — zero dependencies); engine-specific functions that don't
translate are reported as inconclusive, never as failures. Web UI at
`/testgen`, REST under `/api/testgen/` (inline only — the API never writes
files), demo data `examples/testgen_demo/`:

```bash
seatunnel-agent testgen -f query.sql --ddl ddl.sql --out testdata/   # CSV + CREATE + INSERT
seatunnel-agent testgen --sql "SELECT a FROM t WHERE dt='2024-01-01'" --rows 10
seatunnel-agent testgen -f query.sql -F json --no-validate           # machine-readable
seatunnel-agent testgen -f query.sql --fail-on error                 # CI gate (parse/validation)
```

### SeaTunnel Config Deep Lint Agent

The built-in `validate` stops at HOCON syntax and section presence; this
agent lints every parameter against the built-in connector docs (19
connectors): unknown connectors/params get did-you-mean suggestions
(`quary` → `query`, `Consloe` → `Console`), required params are enforced,
values are type- and enum-checked, strictly-source/sink connectors used in
the wrong section are errors, and the env block is sanity-checked (CDC
source + `job.mode = BATCH`, non-positive parallelism). Web UI at
`/conflint`, REST under `/api/conflint/` (whitelisted via
`CONFLINT_API_ALLOWED_DIRS`), demo data `examples/conflint_demo/`:

```bash
seatunnel-agent conflint -f job.conf                                # one file
seatunnel-agent conflint --dir configs/ --fail-on error             # CI gate
seatunnel-agent conflint -c 'source { Consloe {} } sink { Console {} }'
seatunnel-agent conflint --dir configs/ -F json -o lint.json        # machine-readable
```

### Scheduling DAG Health Check Agent

Builds the job DAG from SQL lineage (optionally merged with SeaTunnel
configs) and reports what breaks a scheduler: dependency cycles
(unschedulable), mid-layer tables no job produces (broken upstream),
mid-layer tables nothing consumes (dead jobs), isolated tables — plus
constructive output: topological execution batches (what can run in
parallel, wave by wave) and the critical path bounding end-to-end latency.
Web UI at `/dagcheck`, REST under `/api/dagcheck/` (whitelisted via
`DAGCHECK_API_ALLOWED_DIRS`), demo data `examples/dagcheck_demo/`:

```bash
seatunnel-agent dagcheck -d warehouse_sql/                          # analyze a tree
seatunnel-agent dagcheck -d sql/ --seatunnel-dir confs/ --lang en   # merge config lineage
seatunnel-agent dagcheck -d sql/ -F json --fail-on error            # CI gate on cycles
```

### Metric Consistency Check Agent

Scans column-level lineage for output columns that share one name but are
DEFINED differently across jobs — the number-one cause of "two reports
disagree". Expressions are canonicalized before comparing (aliases and
table qualifiers stripped, `COUNT(1)` ≡ `COUNT(*)`), so formatting
differences never flag; different formulas are **high**
(`gmv = sum(amount)` vs `sum(amount - refund)`), plain copies from
different source columns are **medium** (`contact ← phone` vs `← email`).
Web UI at `/metricdiff`, REST under `/api/metricdiff/` (whitelisted via
`METRICDIFF_API_ALLOWED_DIRS`), demo data `examples/metricdiff_demo/`:

```bash
seatunnel-agent metricdiff -d warehouse_sql/                        # scan a tree
seatunnel-agent metricdiff -d sql/ --fail-on high                   # CI gate
seatunnel-agent metricdiff -d sql/ -F json --lang en                # machine-readable
```

### SQL Formatter Agent

Deterministic sqlglot pretty-printing with a black-style workflow:
`--fail-on change` is the CI check (exit 1 when any file would be
reformatted), `--write` applies in place, and a statement that does not
parse is kept VERBATIM and reported — formatting never destroys content
(files with parse failures are never written). Bare `SELECT *` gets a
style note. Complements SQL Review: that agent judges semantics, this one
makes every script look the same. Web UI at `/sqlfmt` (check-only), REST
under `/api/sqlfmt/` (inline only), demo data `examples/sqlfmt_demo/`:

```bash
seatunnel-agent sqlfmt -s "select a,b from t where dt='2024-01-01'" # inline
seatunnel-agent sqlfmt sql/ --fail-on change                        # CI check (black --check style)
seatunnel-agent sqlfmt sql/ --write                                 # apply in place
seatunnel-agent sqlfmt -d sql/ -F json                              # machine-readable
```

### MCP Toolbox (`seatunnel-agent mcp`)

One stdio MCP server that hands the whole agent suite to any MCP client
(Claude Code / Claude Desktop / Cline / Cursor): SQL review, dialect
translation, data-skew analysis, change-impact diff, DataX/Sqoop migration,
plus schema browsing / **read-only** querying / cross-database row-count &
schema comparison over the saved connections from the Settings page
(referenced by NAME — credentials never enter the model context). Every
tool is deterministic: no LLM calls inside, zero tokens. Lineage tools load
when a graph source is given. Design doc: [`docs/mcp_toolbox.md`](docs/mcp_toolbox.md)

```bash
pip install 'seatunnel-agent[mcp]'
seatunnel-agent mcp                          # 15-tool base set
seatunnel-agent mcp --no-db                  # pure-static profile (6 tools)
seatunnel-agent mcp --connections dev,stage  # allowlist of saved connections
seatunnel-agent mcp --sql-dir sql/           # + lineage tools & data dictionary
seatunnel-agent mcp-stats                    # audit trail of tool calls
claude mcp add seatunnel-agent -- seatunnel-agent mcp   # Claude Code
```

<!-- mcp-name: io.github.clairelytt/seatunnel-agent -->

### UI Testing Agent

Browser-driven regression for the Gradio pages (real Chromium via Playwright,
YAML cases mirroring the 75-item manual checklist, optional LLM steps and
fuzzy assertions):

```bash
python -m seatunnel_agent.ui_testing run --suite smoke --no-llm   # ~3 min, 0 tokens
```

Docs: [`docs/ui_testing_usage.md`](docs/ui_testing_usage.md)

### Troubleshooting

| Problem | Solution |
|---------|----------|
| `RuntimeError: API_KEY is not set` | Create a `.env` file from `.env.example` and fill in your API key: `cp .env.example .env` |
| `Warning: SeaTunnel binary not found` | Set `SEATUNNEL_HOME` in `.env` to your SeaTunnel installation path. This is only needed for `run` and `batch` commands — config generation, validation, and diagnosis work without it. |
| `429 / Rate limit` errors | The agent retries automatically with exponential backoff (1s → 2s → 4s). If it persists, wait a minute or switch to a model with higher rate limits. |
| `ModuleNotFoundError: No module named 'gradio'` | Install with UI support: `pip install -e ".[ui]"` |
| `ModuleNotFoundError: No module named 'anthropic'` | Install the LLM provider you need: `pip install anthropic` or `pip install openai` — or install all: `pip install -e ".[all]"` |
| Chat history not persisted in Docker | Use `docker compose up` — the compose file uses named volumes (`agent-history`, `agent-configs`) for automatic persistence |

### License

MIT

---

<a id="中文"></a>

## 中文

### 功能特性

- **自然语言 → 管道配置**：用自然语言描述需求（"把 MySQL 用户表同步到 Console"），自动生成 HOCON 配置文件
- **自动诊断修复**：作业失败时，Agent 自动读取日志、定位错误、修改配置并重试
- **配置验证**：检查 `.conf` 文件的语法错误和缺失部分，无需运行作业
- **日志诊断**：将 SeaTunnel 日志文件交给 Agent，获取结构化的根因分析
- **配置模板库**：内置 12 个常用模板（FakeSource、MySQL-CDC、Jdbc、Kafka、LocalFile、CSV-MySQL、StarRocks、ClickHouse、Transform），选择模板后 Agent 自动填充参数
- **连接测试**：生成配置前先测试数据库/服务的 TCP 连通性，避免写完配置才发现连不上
- **连接器文档查询**：查询 19 个连接器的参数文档（类型、必填/可选、示例值），在生成配置前确认正确的参数名和格式，减少幻觉和配置错误
- **作业运行指标**：自动解析 SeaTunnel 作业输出，结构化展示运行指标（读取/写入行数、字节数、耗时、状态）
- **配置版本历史**：每次 `write_config` 自动保存带时间戳的版本；可以浏览和比较任何配置文件的历史版本
- **配置版本恢复与删除**：将配置恢复到任意历史版本，或安全删除配置文件（版本历史保留）
- **配置版本对比**：对比两个版本的配置差异，输出 unified diff
- **配置解读**：解析配置文件并生成结构化摘要（作业模式、连接器、参数），适合"这个配置做了什么？"的场景
- **批量任务管理**：顺序执行多个管道配置，返回每个作业的结果和通过/失败汇总；默认遇到第一个失败即停止
- **多轮会话记忆**：Agent 记住本次会话的配置路径、执行结果和连接测试，说"运行刚才的配置"就能直接执行
- **配置 Diff 展示**：覆盖已有配置时，UI 展示新旧配置的 unified diff
- **任务进度可视化**：实时显示步骤计数（含耗时）和流式文本输出（带光标指示符）
- **Token 用量显示**：每次 LLM 调用显示输入/输出 token 数，便于成本感知
- **文件上传**：点击输入框旁的 `+` 按钮上传 `.conf` 文件，自动复制到 configs 目录
- **可点击提示卡片**：点击占位提示即可自动填充输入框
- **导出 ZIP**：下载会话报告（Markdown）+ 所有生成的配置文件
- **停止按钮**：随时中断正在运行的 Agent
- **Web UI**：实时聊天界面，展示 Agent 的思考过程、工具调用和结果 —— 支持中英文双语
- **多模型支持**：Claude、GPT-4o、DeepSeek、Kimi/Moonshot、通义千问、智谱 GLM，以及任何兼容 OpenAI API 的模型
- **LLM 重试与容错**：API 限流 (429) 和服务错误 (500+) 自动指数退避重试
- **DeepSeek 思维链提取**：在 UI 思考面板展示 DeepSeek-R1 的推理过程
- **CLI 增强**：`batch` 批量执行、`--model`/`--provider` 运行时覆盖、`--output` 输出到文件、`chat --resume` 恢复会话
- **演示模式**：无需 API Key 即可体验完整的 Agent 工作流程
- **Text2SQL (Chat BI)**：自然语言数据查询 —— 用中文或英文提问，Agent 自动匹配表、生成安全的 Hive SQL、执行查询并导出 CSV
- **Schema 感知匹配**：基于关键词 + CJK n-gram 模糊匹配，支持表名、列名、中文备注的多维度评分排序
- **分区智能**：自动识别表后缀类型（_di/_hi/_ri = 增量表，_df/_hf = 全量表），从自然语言提取时间范围，生成分区条件
- **SQL 安全验证**：SELECT 白名单、禁止关键词检测、表白名单强制、LIMIT 强制、堆叠查询防护、分区过滤强制、列存在性校验
- **CSV 导出（CJK 支持）**：UTF-8 BOM 编码确保 Excel 正确显示中文，带时间戳的文件名，支持自定义路径
- **结构化查询日志**：JSONL 格式记录每次查询（用户问题、生成 SQL、状态、耗时），便于监控与审计
- **SQL Code Review**：对 Hive/Spark/Flink/MaxCompute SQL 做纯静态审查，无需运行即可发现问题 —— 确定性 Linter（GROUP BY 完整性、笛卡尔积、`= NULL`、分区过滤、除零保护、复杂度评分等）+ LLM 按 15 项检查清单做语义审查，输出固定格式 CR 报告（严重问题/潜在风险/优化建议/检查统计/总体评价）并附表级与列级血缘。支持 `seatunnel-agent review` 命令、REST `POST /api/sql_review/review`、Gradio UI 页面（`/sqlreview`，含历史趋势图），以及无需 API Key 的 `--static-only` 模式。多语句脚本自动按语句拆分审查并映射正确行号。支持目录批量审查（`--dir`）、git 变更文件审查（`--diff`）、位置参数传文件（pre-commit 风格）、CI 门禁（`--fail-on critical|risk|suggestion`）、`.sqlreview.yaml` 规则配置（自定义分区列/关闭检查/调整严重度/自定义正则规则）、行内忽略注释（`-- sqlreview-disable[-next-line|-file][: 类别]`）、基线文件（`--baseline` / `--update-baseline`，只对新问题报错）、机器可读输出（`--format json|sarif`，SARIF 可上传 GitHub Code Scanning，模板见 `examples/ci/` 与 `.pre-commit-hooks.yaml`）、数据库直连拉取表结构（`--db host:port/database`）、LLM 自动生成修复 SQL（`--fix`）与审查历史统计（`review-stats`）
- **变更影响分析**：SQL 变更 × 血缘——对比两份 SQL 目录（或 git 基线）输出上线影响面：破坏性移除 / 口径漂移 / 纯新增三级严重度 + 下游波及深度；CLI `seatunnel-agent impact`（`--fail-on` CI 门禁）、REST `POST /api/lineage/impact`、Web 页面 `/impact`；纯确定性,不连数据库、不调用 LLM
- **SQL 方言翻译**：hive/spark/doris/starrocks 确定性互转（sqlglot）+ 结构化不兼容点清单（解析失败、不支持语法、未知 UDF、存储子句、写侧提示）—— CLI `seatunnel-agent transpile`、REST `/api/transpile/`、Web 页面 `/transpile`；支持目录批量镜像输出、CI 门禁 `--fail-on error|warn`、可选且明确标注的 LLM 建议；不连接数据库、不执行 SQL
- **敏感数据扫描 (PII)**：命名规则 × 字段血缘 —— 用敏感数据规则库匹配列名与中英文注释（手机号、身份证、银行卡、邮箱、地址、工资等），再沿列级血缘追踪下游，标出**未脱敏扩散**（直接复制会升级严重度；`md5()`/`mask()`/`substr()` 链路视为已脱敏）；支持 YAML 自定义规则 —— CLI `seatunnel-agent pii`（`--fail-on high|medium|low`）、REST `/api/pii/`、Web 页面 `/pii`、演示数据 `examples/pii_demo/`；纯确定性，不连数据库、不调用 LLM
- **批量日志巡检**：日志目录异常聚类 —— ERROR/WARN 事件（含完整 Java 堆栈）归一化（数字/路径/地址/ID 打码）后按**根因**聚类（最后一个 `Caused by:` × 消息模板 × 栈顶帧），把嘈杂日志收敛成 Top-N 个不同的问题，附次数、涉及文件与首末时间 —— CLI `seatunnel-agent loginspect`（`--fail-on error|warn`）、REST `/api/loginspect/`、Web 页面 `/loginspect`（可选 llm-generated 建议）、演示数据 `examples/logs_demo/`
- **Schema 漂移检查**：对比两份 DDL 快照（文件/目录/粘贴脚本），每处结构变更分级 —— 破坏（删表删列、不兼容类型变更、分区布局变更）、风险（类型拓宽、疑似改名）、提示（新增、注释变更）—— CLI `seatunnel-agent schemadiff`（`--fail-on breaking|risk|info`）、REST `/api/schemadrift/`、Web 页面 `/schemadrift`、演示数据 `examples/schema_drift_demo/`；与 `/impact` 互补（SQL 逻辑变更 vs 表结构变更）
- **SQL 测试数据生成**：关联感知造数，让查询真正跑通 —— 等值关联列共享取值池（JOIN 必然命中）、WHERE 字面量被满足（并混入一行故意不命中）、混入边界行（NULL/零值/空串），列类型来自 DDL 或按用法推断；可选在内存 SQLite 上做端到端验证（标准库，零依赖）—— CLI `seatunnel-agent testgen`（`--out` 写出 CSV + CREATE + INSERT）、REST `/api/testgen/`、Web 页面 `/testgen`、演示数据 `examples/testgen_demo/`
- **SeaTunnel 配置深度检查**：对照内置连接器文档做 HOCON 参数级 lint —— 未知连接器/参数带「是不是想写」建议、缺失必填参数、类型与枚举校验、source/sink 角色用反、CDC 与 job.mode 冲突、parallelism 合法性 —— CLI `seatunnel-agent conflint`（`--fail-on error|warn`）、REST `/api/conflint/`、Web 页面 `/conflint`、演示数据 `examples/conflint_demo/`；只解析不执行
- **调度 DAG 体检**：从 SQL/SeaTunnel 血缘构建作业 DAG，报告会卡住调度器的问题 —— 依赖成环、没人产出的中间层表（上游断链）、没人消费的中间层表（死作业）—— 并给出建设性输出：拓扑执行分批与关键路径 —— CLI `seatunnel-agent dagcheck`（`--fail-on error|warn`）、REST `/api/dagcheck/`、Web 页面 `/dagcheck`、演示数据 `examples/dagcheck_demo/`
- **指标口径一致性检查**：找出不同作业里同名但定义不同的输出列（「两张报表数对不上」的头号原因）—— 表达式先归一化再比较（去别名/去表前缀、COUNT(1)≡COUNT(*)）：公式不同=高、取自不同来源列=中 —— CLI `seatunnel-agent metricdiff`（`--fail-on high|medium`）、REST `/api/metricdiff/`、Web 页面 `/metricdiff`、演示数据 `examples/metricdiff_demo/`
- **SQL 格式化**：基于 sqlglot 的确定性排版，black 式工作流 —— `--fail-on change` 做 CI 检查、`--write` 写回、解析失败的语句原样保留（格式化永不破坏内容）、裸 `SELECT *` 给风格提示 —— CLI `seatunnel-agent sqlfmt`、REST `/api/sqlfmt/`、Web 页面 `/sqlfmt`、演示数据 `examples/sqlfmt_demo/`
- **三工作区首页**：首页分为 **Data Agents**（`/data`，上述数据能力，分组展示并带即时过滤）、**AI Platform**（`/ai`）与 **DevOps 工作区**（`/devops`）三个工作区，横跨工作区的工程工具（日志巡检、UI 测试、MCP 工具箱、设置）直接放在首页：
- **智能编排** *(AI 平台)*：全平台统一对话入口 —— LLM 把自然语言需求自动路由到合适的确定性 agent（审查/翻译/影响/迁移/倾斜/格式化/配置检查/漂移/PII/造数），在有界 tool-use 循环里自动串联多步，单工具报错隔离；未配置 API key 时退化为关键词推荐（只建议不执行）—— CLI `seatunnel-agent orchestrate`、REST `/api/orchestrator/`、对话页 `/orchestrator`（工具步骤可折叠展开）、示例 `examples/orchestrator_demo/`
- **LLM 评测** *(AI 平台)*：为 LLM 功能（text2sql、sql_review、裸 Prompt）建 YAML 黄金用例集 —— 确定性检查器（`contains`/`regex`/`equals`/`sql_valid`/`json_valid`）自动打分（按 case 加权），运行历史支撑 `--fail-on regression` 回归门禁（case 由过变挂或总分降 >0.01），可选的 LLM judge 仅作参考不进门禁 —— CLI `seatunnel-agent llmeval`、REST `/api/llmeval/`、Web 页面 `/llmeval`（分数趋势图）、示例套件 `examples/llmeval_demo/`
- **Prompt 实验室** *(AI 平台)*：同一 Prompt 在多个模型档案上并排对比（输出、token、耗时、unified diff）—— 每个档案构造独立 Settings，绝不切换全局配置，档案密钥永不外泄（API 只返回档案名）—— CLI `seatunnel-agent promptlab`、REST `/api/promptlab/`、Web 页面 `/promptlab`、示例 Prompt `examples/promptlab_demo/`
- **LLM 成本观测** *(AI 平台)*：基于全平台调用日志的成本看板 —— 近似价格表（最长前缀匹配，YAML 可覆盖）按模型/按天/按 agent 汇总，前 7 天均值异常日标记，`--fail-on budget` 预算门禁 —— CLI `seatunnel-agent llmcost`、REST `/api/llmcost/`、Web 页面 `/llmcost`（堆叠成本图）、演示数据 `examples/llmcost_demo/`
- **敏感凭证扫描** *(DevOps)*：找出代码与配置里的泄漏凭证 —— 云厂商 token（AWS/GitHub/GitLab/Slack/阿里云）、私钥块、明文密码/API Key 赋值、DSN 内嵌密码与高熵字符串；占位符自动过滤，预览永远脱敏，单行 pragma 或 `.secretscan.yaml` 可豁免 —— CLI `seatunnel-agent secretscan --fail-on high|medium|low`、REST `/api/secretscan/`、Web 页面 `/secretscan`、演示数据 `examples/secretscan_demo/`
- **CI 日志诊断** *(DevOps)*：失败作业日志聚类成 Top-N 根因（聚类前掩掉数字/路径/哈希），运行元数据分析 flaky（同一提交又过又挂）与时长漂移；`--gh owner/repo` 可用 gh CLI 拉取最近运行 —— CLI `seatunnel-agent ciinspect --fail-on flaky`、REST `/api/ciinspect/`、Web 页面 `/ciinspect`、演示数据 `examples/ciinspect_demo/`
- **依赖体检** *(DevOps)*：离线检查 pyproject/requirements —— 声明未装或版本违反（高危）、未钉版本/重复冲突声明/copyleft License（中危）、License 缺失（提示），附完整依赖清单 —— CLI `seatunnel-agent depcheck --fail-on high|medium`、REST `/api/depcheck/`、Web 页面 `/depcheck`、演示数据 `examples/depcheck_demo/`
- **发布助手** *(DevOps)*：按 conventional commits 分组生成 changelog（破坏性变更单列）+ 语义化版本建议（breaking→major、feat→minor、否则 patch）；可选 LLM 润色（仅参考，失败回退）—— CLI `seatunnel-agent relnotes`（`--log-file` 离线输入）、REST `/api/release/`、Web 页面 `/release`、演示数据 `examples/release_demo/`

### 快速开始

#### 前置条件

- Python 3.10+
- LLM API Key（Anthropic / OpenAI / DeepSeek / Kimi / Qwen / GLM 任选一个）
- Apache SeaTunnel（可选 —— 生成配置、验证、诊断功能不需要安装 SeaTunnel）

#### 第一步：克隆并安装

```bash
git clone https://github.com/ClaireLytt/seatunnel_agent.git
cd seatunnel_agent

# 安装 Web UI + 所有 LLM 支持
pip install -e ".[all,ui]"
```

<details>
<summary>其他安装方式</summary>

```bash
# 仅 CLI（不含 UI）
pip install -e .

# 安装特定 LLM
pip install -e ".[ui]"
pip install anthropic    # 使用 Claude
pip install openai       # 使用 DeepSeek/Kimi/Qwen/GPT

# 开发环境（含测试依赖）
pip install -e ".[dev]"
```

</details>

#### 第二步：配置 `.env`

> 💡 **免改文件的方式：** 启动 Web 界面后打开「设置」页（`/settings`），提供商、API Key、
> 模型、Base URL 都可以直接在浏览器里填写（Key 加密保存在 `~/.seatunnel-agent/` 下），
> 保存即生效，并覆盖 `.env` 中的同名配置，点「恢复 .env」即可还原。页面还提供命名
> **配置档案**（每个提供商一套，一键切换）、**数据库连接**管理（与数据对比页预设共用）、
> 真实**连接测试**，以及近 30 天 **LLM token 用量**汇总（CLI：`seatunnel-agent settings --usage`）。
> CLI 运行仍读取 `.env`。

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 必填：你的 LLM API Key
API_KEY=sk-your-api-key-here

# LLM 提供商："anthropic" 或 "openai"（所有兼容 OpenAI API 的都用 openai）
LLM_PROVIDER=anthropic

# 模型名称（默认 claude-opus-5）
MODEL_NAME=claude-opus-5

# 非默认 API 地址（DeepSeek、Kimi、Qwen 等需要设置）
# LLM_BASE_URL=https://api.deepseek.com

# SeaTunnel 安装路径（可选）
# SEATUNNEL_HOME=/opt/apache-seatunnel

# 失败重试次数（默认 3）
# MAX_RETRIES=3

# 作业执行超时（秒，默认 120）
# JOB_TIMEOUT=120

# LLM 温度（默认 0.0，确定性输出）
# TEMPERATURE=0.0

# 生成配置的目录（默认 configs）
# CONFIG_DIR=configs
```

<details>
<summary>各 LLM 配置示例</summary>

**DeepSeek**
```env
LLM_PROVIDER=openai
API_KEY=sk-your-deepseek-key
MODEL_NAME=deepseek-chat
LLM_BASE_URL=https://api.deepseek.com
```

**Kimi / Moonshot**
```env
LLM_PROVIDER=openai
API_KEY=sk-your-kimi-key
MODEL_NAME=kimi-k2.7-code
LLM_BASE_URL=https://api.moonshot.cn/v1
```

**通义千问 (Qwen)**
```env
LLM_PROVIDER=openai
API_KEY=sk-your-qwen-key
MODEL_NAME=qwen-plus
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
```

**智谱 GLM**
```env
LLM_PROVIDER=openai
API_KEY=your-glm-key
MODEL_NAME=glm-4
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
```

**OpenAI**
```env
LLM_PROVIDER=openai
API_KEY=sk-your-openai-key
MODEL_NAME=gpt-4o
```

</details>

#### 第三步：启动

```bash
# 启动 Web UI（自动打开浏览器）
seatunnel-agent ui

# 或使用命令行
seatunnel-agent run --task "生成 10 条假数据输出到控制台"
```

#### 第四步（可选）：配置 Text2SQL (Chat BI)

Text2SQL 支持 8 种数据库引擎。安装对应数据库驱动：

```bash
pip install -e ".[mysql]"       # MySQL / Doris
pip install -e ".[postgres]"    # PostgreSQL
pip install -e ".[hive]"        # Hive / Spark SQL
pip install -e ".[sqlserver]"   # SQL Server
pip install -e ".[clickhouse]"  # ClickHouse
pip install -e ".[db-all]"      # 全部数据库驱动
pip install -e ".[chart]"       # 图表可视化（matplotlib）
```

在 `.env` 中添加数据库连接配置（以 MySQL 为例）：

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DATABASE=mydb
MYSQL_USERNAME=readonly_user
MYSQL_PASSWORD=secret
```

所有支持的引擎配置请参考 `.env.example`（Hive、Spark SQL、MySQL、SQL Server、ClickHouse、Doris、PostgreSQL）。建议使用只读数据库账号。

可选：在 `config/schema_ddl.sql` 中填入表 DDL 作为白名单，限制 Agent 可查询的表范围。不配置白名单时，连接数据库中的所有表均可查询。

### Docker 部署

使用 Docker 运行（无需安装 Python）：

```bash
# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填入你的 API Key

# 2. 构建并运行
docker compose up --build

# 打开 http://localhost:7860
```

或手动构建：

```bash
docker build -t seatunnel-agent .
docker run -p 7860:7860 --env-file .env seatunnel-agent
```

### Web UI 使用指南

启动 Web UI：

```bash
seatunnel-agent ui

# 局域网访问
seatunnel-agent ui --host 0.0.0.0
# 浏览器自动打开 http://127.0.0.1:7860
```

#### 界面布局

```
┌──────────────┬─────────────────────────────────────────┐
│    侧边栏    │                            [语言: 中文] │
│              │                                         │
│ [+ 新建对话] │     ┌──────────────────────────┐        │
│              │     │         ST logo           │        │
│  历史记录 ▼  │     │  我能帮你构建什么管道？    │        │
│  ├─ 对话 1   │     │                           │        │
│  └─ 对话 2   │     │  [提示 1] [提示 2] [提示3]│        │
│              │     │       📖 文档              │        │
│  模板 ▼      │     └──────────────────────────┘        │
│  运行模式 ▼  │                                         │
│  配置路径    │  ┌──────────────────────────────────┐   │
│  [连接]      │  │ [+] [输入框]    [演示] [■] [➤]│   │
│  状态        │  └──────────────────────────────────┘   │
│  [导出]      │                                         │
└──────────────┴─────────────────────────────────────────┘
```

#### 使用步骤

1. **连接 LLM**：点击侧边栏的 **连接** 按钮。如果 `.env` 配置正确，状态栏显示 `✅ 连接成功，模型: xxx`

2. **选择模式**：
   | 模式 | 功能 |
   |------|------|
   | 自然语言描述 | 输入自然语言任务 → Agent 自动生成并运行配置 |
   | 运行配置文件 | 指定 `.conf` 文件 → Agent 运行并自动修复错误 |
   | 验证配置 | 检查配置文件的语法和结构问题，不运行作业 |
   | 诊断日志 | 分析 SeaTunnel 日志文件，找出错误根因 |

3. **发送消息**：在底部输入框输入任务描述，点击 **发送** 或按回车键

4. **观察 Agent 工作过程**：聊天窗口实时展示：
   - 💭 **思考** — Agent 的推理过程
   - 🔧 **工具调用** — 正在调用哪个工具，传了什么参数
   - ✅/❌ **结果** — 工具返回的结果（成功/失败）
   - 最终答案：生成的配置或诊断结果

5. **演示模式**：点击 **演示** 按钮，无需 API Key 即可体验完整工作流。使用本地工具模拟 Agent 流程。

6. **管理对话**：
   - **+ 新建对话**：开始新的对话
   - **历史记录**：点击之前的对话可以重新加载
   - **重命名 / 删除**：选中一个对话后，会出现重命名和删除按钮

7. **切换语言**：使用右上角的语言下拉菜单，在中文和英文之间切换

#### 分享给他人

生成临时公网链接（72 小时有效）：

```bash
seatunnel-agent ui --share
```

这会创建一个 `https://xxxxx.gradio.live` 链接，任何人都可以通过这个链接访问。你的电脑需要保持开机且程序运行中。

自定义端口：

```bash
seatunnel-agent ui --port 8080
```

### CLI 命令行用法

```bash
# 自然语言描述任务
seatunnel-agent run --task "生成 10 条假数据，字段为 id、name、age，输出到控制台"

# 运行已有配置（失败自动修复）
seatunnel-agent run --config examples/fake_to_console.conf

# 输出结果到文件
seatunnel-agent run --task "..." --output result.txt

# 验证配置文件
seatunnel-agent validate --config examples/fake_to_console.conf

# 诊断日志
seatunnel-agent diagnose --log /path/to/seatunnel.log

# 批量执行多个配置
seatunnel-agent batch -c config1.conf -c config2.conf --stop-on-failure

# 交互式对话（支持恢复会话）
seatunnel-agent chat
seatunnel-agent chat --list-sessions          # 列出已保存的会话
seatunnel-agent chat --resume <session_id>    # 恢复指定会话

# 运行时指定模型/提供商
seatunnel-agent --model deepseek-chat --provider openai run --task "..."

# 详细输出
seatunnel-agent -v run --task "..."
```

### Text2SQL (Chat BI) 使用说明

Text2SQL 功能支持自然语言查询 Hive 表数据。通过 Web UI 的 **Text2SQL** 页面访问。

#### 工作流程

```
用户问题（自然语言）
    │
    ▼
┌─────────────────────────────────────────┐
│       Text2SQL Agent (ReAct 循环)        │
│                                         │
│  1. match_tables    → 匹配候选表         │
│  2. get_table_schema → 查看列信息        │
│  3. get_max_partition → 获取最新分区      │
│  4. 生成 SQL         → LLM + 规则       │
│  5. execute_sql     → 验证并执行         │
│  6. export_csv      → 导出结果           │
└─────────────────────────────────────────┘
    │
    ▼
Hive SQL 查询结果 + CSV 导出
```

#### 示例查询

| 问题 | 生成的 SQL（简化） |
|------|-------------------|
| "查询最近7天的入库单量" | `SELECT COUNT(*) FROM zz.dwm_scm_detail_di WHERE pt >= '20260907' AND pt <= '20260914'` |
| "各品牌的入库总量" | `SELECT brand_name, SUM(inbound_cnt) FROM ... WHERE pt = '<max>' GROUP BY brand_name` |
| "查询学生表所有数据" | `SELECT * FROM atest.student LIMIT 1000` |

#### 安全保障

- **仅允许 SELECT**：写操作（INSERT/UPDATE/DELETE/DROP/ALTER）被强制拦截
- **表白名单**：仅能查询 `config/schema_ddl.sql` 中定义的表
- **分区过滤强制**：分区表必须带分区过滤条件，否则查询被拒绝
- **行数限制**：每条查询自动添加 LIMIT（默认 1000，最大 100,000）
- **查询日志**：所有查询记录到 `logs/text2sql_queries.jsonl`

### 支持的 LLM

| 提供商 | 模型示例 | 配置 |
|--------|---------|------|
| Anthropic (Claude) | claude-opus-5, claude-sonnet-5 | `LLM_PROVIDER=anthropic` |
| OpenAI | gpt-4o, gpt-4o-mini | `LLM_PROVIDER=openai` |
| DeepSeek | deepseek-chat, deepseek-reasoner | `LLM_PROVIDER=openai` + `LLM_BASE_URL=https://api.deepseek.com` |
| Kimi/Moonshot | kimi-k2.7-code | `LLM_PROVIDER=openai` + `LLM_BASE_URL=https://api.moonshot.cn/v1` |
| 通义千问 (Qwen) | qwen-plus, qwen-turbo | `LLM_PROVIDER=openai` + `LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 智谱 GLM | glm-4 | `LLM_PROVIDER=openai` + `LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4` |

所有兼容 OpenAI API 格式的模型均可使用，只需设置 `LLM_PROVIDER=openai` 并配置对应的 `LLM_BASE_URL`。

### 架构

```
用户输入（自然语言）
    │
    ├───────────────────────┐
    ▼                       ▼
┌──────────────────┐  ┌──────────────────────┐
│  SeaTunnel Agent │  │  Text2SQL Agent      │
│  (管道构建)       │  │  (Chat BI)           │
│                  │  │                      │
│  ┌────────────┐  │  │  ┌────────────────┐  │
│  │  LLM +     │  │  │  │ LLM + Schema   │  │
│  │  ReAct     │  │  │  │ Store + ReAct  │  │
│  │  循环       │  │  │  │ 循环           │  │
│  └─────┬──────┘  │  │  └──────┬─────────┘  │
│        │         │  │         │             │
│  ┌─────▼──────┐  │  │  ┌──────▼─────────┐  │
│  │ 16 个工具   │  │  │  │  5 个工具      │  │
│  │ run_job    │  │  │  │ match_tables   │  │
│  │ read/write │  │  │  │ get_schema     │  │
│  │ validate   │  │  │  │ get_partition  │  │
│  │ diagnose   │  │  │  │ execute_sql    │  │
│  │ templates  │  │  │  │ export_csv     │  │
│  │ ...        │  │  │  └────────────────┘  │
│  └────────────┘  │  │                      │
└────────┬─────────┘  └──────────┬───────────┘
         │                       │
         ▼                       ▼
  Apache SeaTunnel         HiveServer2
  （数据集成引擎）          （数据查询）
```

### 项目结构

```
seatunnel_agent/
├── pyproject.toml              # 项目配置与依赖
├── .env.example                # 环境变量模板
├── Dockerfile                  # Docker 镜像构建
├── docker-compose.yml          # Docker Compose（含持久化卷）
├── config/
│   └── schema_ddl.sql          # Text2SQL 表白名单（Hive CREATE TABLE DDL）
├── src/seatunnel_agent/
│   ├── config.py               # 配置加载（.env → Settings）
│   ├── llm.py                  # 多模型 LLM 抽象层
│   ├── utils.py                # 工具函数
│   ├── tools.py                # 16 个工具定义 + 执行器（SeaTunnel 管道）
│   ├── templates.py            # 12 个内置管道配置模板
│   ├── connector_docs.py       # 连接器参数文档（19 个连接器）
│   ├── prompts.py              # System Prompt（SeaTunnel 管道 Agent）
│   ├── agent.py                # ReAct 循环 + 会话上下文追踪
│   ├── history.py              # 对话历史持久化
│   ├── cli.py                  # Click CLI 入口
│   ├── ui.py                   # Gradio Web UI 主页（多页应用）
│   ├── text2sql_ui.py          # Gradio Text2SQL 页面（流式聊天）
│   └── text2sql/               # Text2SQL (Chat BI) Agent 包
│       ├── __init__.py         # 包导出
│       ├── schema.py           # DDL 解析器、SchemaStore、表/列模型
│       ├── matcher.py          # 表/列模糊匹配（关键词 + CJK n-gram）
│       ├── partition.py        # 分区分类、时间范围提取
│       ├── validator.py        # SQL 安全（SELECT 白名单、表白名单、列校验、LIMIT）
│       ├── chart.py            # 自动检测图表类型 + matplotlib 渲染
│       ├── favorites.py        # SQL 收藏夹（JSON 后端）
│       ├── i18n.py             # UI 国际化字典（中英文）
│       ├── exporter.py         # CSV 导出（UTF-8 BOM 支持 Excel）
│       ├── prompts.py          # System Prompt 组装（规则 + Schema）
│       ├── tools.py            # 5 个工具定义 + 运行时 + 分区强制
│       ├── agent.py            # ReAct 循环、事件协议、多轮对话
│       ├── qlog.py             # 结构化查询日志（JSONL）
│       ├── executor/           # 多引擎数据库执行器
│       │   ├── base.py         # 抽象基类、工厂、DatabaseConfig
│       │   ├── hive.py         # HiveServer2（pyhive）
│       │   ├── mysql.py        # MySQL（pymysql）
│       │   ├── postgres.py     # PostgreSQL（psycopg2）
│       │   ├── sqlserver.py    # SQL Server（pymssql）
│       │   ├── clickhouse.py   # ClickHouse（clickhouse-connect）
│       │   ├── doris.py        # Doris/StarRocks（MySQL 协议）
│       │   ├── spark.py        # Spark SQL（扩展 Hive）
│       │   └── flink.py        # Flink SQL（仅生成）
│       └── resources/
│           ├── SKILL.md        # 技能入口（触发条件、工作流程）
│           ├── intent_rules.md # 业务规则（分区、聚合等）
│           └── optimize_rules.md # Spark/Hive 性能优化规则
├── scripts/                    # 开发工作流脚本
│   ├── ship.ps1                # 提交并推送到当前分支
│   └── next.ps1                # 同步 main，创建新分支
├── docs/
│   └── text2sql_test_doc.md    # Text2SQL 测试文档（62 自动化 + 手动测试用例）
├── tests/                      # 369 个单元测试
│   ├── test_config.py          # Settings 与环境变量
│   ├── test_tools.py           # 16 个工具、路径安全守卫、版本碰撞修复、指标解析、批量任务
│   ├── test_templates.py       # 模板注册、渲染、分类、工具集成
│   ├── test_connector_docs.py  # 连接器文档查询与查找
│   ├── test_agent.py           # ReAct 循环、上下文追踪（全部 16 个工具）、重试上限退出
│   ├── test_history.py         # 会话持久化、session_id 安全校验、上下文字段
│   ├── test_llm.py             # LLM 客户端、重试逻辑（字符串状态码处理）、Token 用量、DeepSeek 思维链
│   ├── test_prompts.py         # System Prompt 内容验证
│   ├── test_ui_format.py       # 事件格式化、导出、耗时展示、Token 用量显示、工具 Emoji、EventCollector
│   ├── test_utils.py           # 工具函数（truncate、日志解析）
│   ├── test_cli.py             # CLI 命令、批量任务、--list-sessions
│   └── test_text2sql.py        # Text2SQL：Schema、验证、匹配、分区、工具层（62 个测试）
└── examples/                   # 示例配置
    ├── fake_to_console.conf
    └── mysql_to_console.conf
```

### 测试

```bash
# 运行全部 369 个测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_agent.py -v

# 仅运行 Text2SQL 测试
pytest tests/test_text2sql.py -v

# 生成覆盖率报告
pytest tests/ --cov=seatunnel_agent --cov-report=term-missing
```

各模块测试覆盖：

| 模块 | 测试数 | 覆盖范围 |
|------|--------|----------|
| `config.py` | 14 | Settings 加载、环境变量（JOB_TIMEOUT、TEMPERATURE、CONFIG_DIR、MAX_TOKENS）、Provider 验证 |
| `tools.py` | 67 | 全部 16 个工具、路径安全守卫、扩展名验证、版本碰撞修复、Diff 生成、指标解析、批量任务 |
| `templates.py` | 25 | 12 个模板：注册、渲染、分类、参数验证、工具集成 |
| `connector_docs.py` | 25 | 19 个连接器：查询、参数详情、大小写无关查找、类型验证 |
| `agent.py` | 28 | ReAct 循环、上下文追踪（全部 16 个工具）、重试上限退出、入口函数 |
| `history.py` | 29 | 保存/加载、重命名、删除、session_id 安全校验、上下文字段、路径迁移 |
| `llm.py` | 31 | Anthropic 与 OpenAI 客户端、重试逻辑（字符串状态码）、Token 用量提取、DeepSeek 思维链 |
| `prompts.py` | 13 | System Prompt 内容、任务提示、工具引用 |
| `ui.py` | 49 | 事件格式化、导出、耗时展示、Token 用量显示、工具 Emoji、EventCollector |
| `utils.py` | 17 | truncate、find_latest_log、safe_json、resolve_log_path |
| `cli.py` | 9 | CLI 命令、批量任务、--list-sessions |
| `text2sql/` | 62 | Schema 解析、SQL 验证（SELECT 白名单、表白名单、堆叠查询）、表/列匹配、分区规则、CSV 导出、查询日志、列校验、分区强制、工具层、边缘用例 |

完整的 Text2SQL 测试文档：[`docs/text2sql_test_doc.md`](docs/text2sql_test_doc.md)

### 数据血缘 Agent

从 SQL 文件 / SeaTunnel 配置 / Hive 元数据血缘表构建表级与字段级全链路血缘——
上下游链路、字段影响分析、SLA 影响、治理体检、快照对比与 OpenLineage 导出。
Web 页面 `/lineage`,CLI:

```bash
seatunnel-agent lineage --sql-dir examples/lineage_demo -t dws.gmv_daily            # 链路报告
seatunnel-agent lineage --sql-dir sql/ -t dwd.orders_di -c amount                   # 字段影响
seatunnel-agent lineage --sql-dir sql/ --check                                      # 治理体检
seatunnel-agent lineage --sql-dir sql/ --ask "改 orders 的 amount 影响哪些下游?"     # Agent 模式
seatunnel-agent lineage-mcp --sql-dir sql/                                          # MCP server (stdio)
```

### 数据字典生成

从血缘图直接产出 Markdown 数据字典——每张表的分层、上下游、全部字段及其
来源与表达式（聚合字段打标）。纯确定性；`--describe` 可选用 LLM 为每表补
一句描述（明确标注 `llm-generated`）：

```bash
seatunnel-agent datadict -d examples/lineage_demo -o dict.md
seatunnel-agent datadict -d sql/ --lang en --describe
```

### 变更影响分析 Agent

SQL 变更 × 血缘下游遍历：对比两份 SQL（两个目录、工作区 vs git 基线，或直接粘贴两段 SQL，粘贴模式可带上下文 SQL 目录，让片段的下游波及覆盖全仓真实消费方），
输出上线影响面报告（含按严重度染色的 mermaid 影响图）——哪些目标表变了（新增 / 移除 / 字段口径漂移）、下游波及
哪些表、波及多深，并按严重度分级（`error` 破坏性移除 / `warn` 有消费方的
口径变更 / `info` 纯新增），可用 `--fail-on` 做 CI 门禁。纯确定性——不连接
数据库、不调用 LLM。Web 页面 `/impact`，REST
`POST /api/lineage/impact`，MCP 工具（`lineage-mcp` server 上的
`lineage_change_impact`），CI 门禁模板 `examples/ci/*impact*`，演示数据
`examples/impact_demo/`：

```bash
seatunnel-agent impact --old-dir examples/impact_demo/old --sql-dir examples/impact_demo/new
seatunnel-agent impact --base origin/main --sql-dir sql/                # git 基线模式
seatunnel-agent impact --old-dir old/ --sql-dir new/ -F json --fail-on error   # CI 门禁
seatunnel-agent impact --base origin/main --sql-dir sql/ -F md-comment          # PR 评论用精简 markdown
seatunnel-agent impact-stats                                                    # 分析历史与高频变更表
```

### DataX/Sqoop 迁移 Agent

规则驱动的确定性转换:DataX job JSON 与 sqoop import/export 命令行一键转
SeaTunnel 配置——jdbc 读写(column/where 组 query、splitPk → partition_column、
speed.channel → parallelism)、doris/starrocks/hdfs/本地文件/stream 插件;
所有映射不了的参数都进迁移说明清单(绝不静默丢弃,未知插件产出 error +
TODO 块)。Web 页面 `/migrate`,演示数据 `examples/migrate_demo/`:

```bash
seatunnel-agent migrate examples/migrate_demo/01_mysql_to_doris.json -o job.conf
seatunnel-agent migrate -D datax_jobs/ -o seatunnel_confs/           # 批量,镜像目录
seatunnel-agent migrate -D datax_jobs/ -F json --fail-on error       # CI 门禁
```

### SQL 方言翻译 Agent

hive / spark / doris / starrocks / mysql / presto(trino) / clickhouse 七方言互转——基于 sqlglot 的确定性翻译
（同一输入产出恒定，`--no-llm`、无 API key 均可用），并输出结构化不兼容点
清单：解析失败、目标方言不支持语法、未知 UDF、存储子句（`STORED AS` /
`TBLPROPERTIES`）、写侧提示（`DISTRIBUTE BY`）与 `INSERT ... PARTITION`
差异说明。可选的 LLM 建议单独呈现并明确标注 `llm-generated`，不覆盖
确定性结果。不连接数据库、不执行 SQL。Web 页面 `/transpile`，REST 接口
`/api/transpile/`，演示数据 `examples/transpile_demo/`：

```bash
seatunnel-agent transpile --from hive --to doris query.sql                          # 单文件
seatunnel-agent transpile --to starrocks -s "SELECT get_json_object(p,'$.a') FROM t" # 内联（自动推断源方言）
seatunnel-agent transpile --from hive --to doris -D sql/ -o doris_sql/              # 批量,镜像目录输出
seatunnel-agent transpile --to doris -D sql/ -F json --no-llm --fail-on error       # CI 门禁
```

### 数据倾斜分析 Agent

13 条静态规则识别易倾斜 SQL 写法（COUNT(DISTINCT) 单点聚合、NULL 关联键、
JOIN 键套函数、全局 ORDER BY / DISTINCT / UNION 去重、动态分区写入未打散、
缺广播提示等），并用 LLM 改写优化（加盐、两阶段聚合、skew-join 提示）。
支持 Spark SQL / MaxCompute SQL（Hive 作为兼容输入）。可选连接数据源，
用真实键值分布探查**验证**倾斜（并行探查、支持 TABLESAMPLE 采样，实测
热点值回灌改写 prompt 与引擎参数建议），并对原 SQL 与优化 SQL 做**一致性
实测**（小结果集逐行比对，大结果集逐列聚合指纹）。实测确认的倾斜还会生成
填入实测值的确定性改写模板。Web 页面 `/dataskew`（分析历史、SQL 文件上传、
与设置页共享已保存连接、SQL 审查页一键跳转带入 SQL），REST 接口
`/api/skew/`；静态扫描是确定性的——无需 API key、不执行 SQL：

```bash
seatunnel-agent skew -s "SELECT count(distinct uid) FROM t"          # 内联,静态扫描
seatunnel-agent skew -f etl.sql --dialect maxcompute --lang en       # 单文件
seatunnel-agent skew -D sql/ --fail-on high                          # 目录级 CI 门禁
seatunnel-agent skew -f etl.sql --llm -o report.md                   # + LLM 改写
seatunnel-agent skew-stats                                           # history & aggregates
seatunnel-agent skew-mcp                                             # MCP server (stdio)
```

### 敏感数据扫描 Agent (PII)

命名规则 × 字段血缘：内置规则库（手机号、身份证、银行卡、邮箱、姓名、
地址、工资、生日、车牌、IP 等）同时匹配 `CREATE TABLE` 的**列名与中文
注释**，以及血缘列边中出现的列。每个命中再沿列级血缘下探：报告给出敏感
值扩散到了哪些下游表列、每条传播边是否脱敏（`md5`/`sha2`/`mask`/
`substr` 等视为已脱敏，直接复制视为未脱敏）——存在未脱敏扩散时严重度
升一级；已经哈希过的列（`phone_md5`）自动降为低风险。支持 YAML 追加
自定义规则。Web 页面 `/pii`，REST `/api/pii/`（目录白名单
`PII_API_ALLOWED_DIRS`），演示数据 `examples/pii_demo/`；纯确定性——
不连数据库、不调用 LLM：

```bash
seatunnel-agent pii --dir warehouse_sql/                             # 扫描目录
seatunnel-agent pii --sql "CREATE TABLE t (phone STRING COMMENT '手机号');"
seatunnel-agent pii --dir sql/ --rules my_rules.yaml --lang en       # 自定义规则
seatunnel-agent pii --dir sql/ -F json --fail-on high                # CI 门禁
```

### 批量日志巡检 Agent

日志目录异常聚类：ERROR/WARN 行与完整 Java 堆栈组装成事件，归一化易变
片段（数字/路径/地址/ID）后按**根因**聚类——最后一个 `Caused by:` 异常 ×
消息模板 × 栈顶帧——同一故障在不同任务/文件中的反复出现归入同一簇，
附次数、首末时间与代表样本。Web 页面 `/loginspect`（可选 `llm-generated`
根因建议），REST `/api/loginspect/`（目录白名单
`LOGINSPECT_API_ALLOWED_DIRS`），演示数据 `examples/logs_demo/`：

```bash
seatunnel-agent loginspect --dir logs/                               # 聚类整个目录
seatunnel-agent loginspect --dir logs/ --no-warn --top 5             # 只看 error,前 5 簇
seatunnel-agent loginspect -f seatunnel.log --lang en                # 单文件
seatunnel-agent loginspect --dir logs/ -F json --fail-on error       # CI 门禁
```

### Schema 漂移检查 Agent

对比两份 Schema 快照（CREATE TABLE 脚本——文件/目录/粘贴 DDL），每处
变更分级：**破坏**（删表删列、不兼容类型变更、分区布局变更）、**风险**
（拓宽类型变更如 INT→BIGINT / DECIMAL(10,2)→DECIMAL(16,2)、疑似改名——
类型与注释一致）、**提示**（新增表列、注释变更）。与变更影响分析互补：
`/impact` 管 SQL 逻辑变更，这里管表结构变更。Web 页面 `/schemadrift`，
REST `/api/schemadrift/`（路径白名单 `SCHEMADRIFT_API_ALLOWED_DIRS`），
演示数据 `examples/schema_drift_demo/`：

```bash
seatunnel-agent schemadiff --old ddl_v1/ --new ddl_v2/               # 两个目录
seatunnel-agent schemadiff --old old.sql --new new.sql --lang en     # 两个文件
seatunnel-agent schemadiff --old v1/ --new v2/ -F json --fail-on breaking  # CI 门禁
```

### SQL 测试数据生成 Agent

为查询生成最小可用的逐表测试数据集：等值关联列共享取值池（JOIN 必然
命中，单源 CTE 也能穿透）、WHERE 字面量（`dt = '...'`、`status IN
(...)`、BETWEEN）被大多数行满足——并混入一行故意不命中，证明过滤条件
真实生效——再混入边界行（NULL/零值/空串）。列类型优先取自 DDL，否则按
字面量、用法与命名推断。生成的数据 + 查询可在内存 SQLite 上做端到端
验证（标准库，零依赖）；无法翻译的引擎特有函数报告为"结果不确定"，
绝不误报失败。Web 页面 `/testgen`，REST `/api/testgen/`（仅内联，API
不写文件），演示数据 `examples/testgen_demo/`：

```bash
seatunnel-agent testgen -f query.sql --ddl ddl.sql --out testdata/   # CSV + CREATE + INSERT
seatunnel-agent testgen --sql "SELECT a FROM t WHERE dt='2024-01-01'" --rows 10
seatunnel-agent testgen -f query.sql -F json --no-validate           # 机器可读输出
seatunnel-agent testgen -f query.sql --fail-on error                 # CI 门禁（解析/验证）
```

### SeaTunnel 配置深度检查 Agent

内置的 `validate` 只查 HOCON 语法和配置段是否存在；这个 agent 对照内置
连接器文档（19 个连接器）逐参数检查：未知连接器/参数带「是不是想写」
建议（`quary` → `query`、`Consloe` → `Console`）、必填参数强制校验、
取值做类型与枚举检查、只能做 source/sink 的连接器用错段算错误，env 段
做合法性检查（CDC 源 + `job.mode = BATCH`、非正 parallelism）。Web 页面
`/conflint`，REST `/api/conflint/`（白名单 `CONFLINT_API_ALLOWED_DIRS`），
演示数据 `examples/conflint_demo/`：

```bash
seatunnel-agent conflint -f job.conf                                # 单文件
seatunnel-agent conflint --dir configs/ --fail-on error             # CI 门禁
seatunnel-agent conflint -c 'source { Consloe {} } sink { Console {} }'
seatunnel-agent conflint --dir configs/ -F json -o lint.json        # 机器可读
```

### 调度 DAG 体检 Agent

从 SQL 血缘（可选合并 SeaTunnel 配置血缘）构建作业 DAG，报告会卡住
调度器的问题：依赖成环（无法调度）、没人产出的中间层表（上游断链）、
没人消费的中间层表（死作业）、孤立表 —— 并给出建设性输出：拓扑执行
分批（哪些表能并行、分几波跑）和决定端到端时延的关键路径。Web 页面
`/dagcheck`，REST `/api/dagcheck/`（白名单 `DAGCHECK_API_ALLOWED_DIRS`），
演示数据 `examples/dagcheck_demo/`：

```bash
seatunnel-agent dagcheck -d warehouse_sql/                          # 分析整个目录
seatunnel-agent dagcheck -d sql/ --seatunnel-dir confs/ --lang en   # 合并配置血缘
seatunnel-agent dagcheck -d sql/ -F json --fail-on error            # 环检测 CI 门禁
```

### 指标口径一致性检查 Agent

扫描列级血缘，找出同名但在不同作业里**定义不同**的输出列 ——「两张报表
数对不上」的头号原因。表达式先归一化再比较（去别名/去表前缀、
`COUNT(1)` ≡ `COUNT(*)`），排版差异不会误报；公式不同是**高**风险
（`gmv = sum(amount)` vs `sum(amount - refund)`），同名复制自不同来源列
是**中**风险（`contact ← phone` vs `← email`）。Web 页面 `/metricdiff`，
REST `/api/metricdiff/`（白名单 `METRICDIFF_API_ALLOWED_DIRS`），演示
数据 `examples/metricdiff_demo/`：

```bash
seatunnel-agent metricdiff -d warehouse_sql/                        # 扫描整个目录
seatunnel-agent metricdiff -d sql/ --fail-on high                   # CI 门禁
seatunnel-agent metricdiff -d sql/ -F json --lang en                # 机器可读
```

### SQL 格式化 Agent

基于 sqlglot 的确定性排版，black 式工作流：`--fail-on change` 做 CI
检查（有文件需要重排就退 1）、`--write` 原地写回、解析失败的语句**原样
保留**并报告 —— 格式化永不破坏内容（有解析失败的文件绝不写回）。裸
`SELECT *` 给风格提示。与 SQL Review 互补：那边管语义质量，这边让所有
脚本长一个样。Web 页面 `/sqlfmt`（只检查不写文件），REST
`/api/sqlfmt/`（仅内联），演示数据 `examples/sqlfmt_demo/`：

```bash
seatunnel-agent sqlfmt -s "select a,b from t where dt='2024-01-01'" # 内联
seatunnel-agent sqlfmt sql/ --fail-on change                        # CI 检查（black --check 式）
seatunnel-agent sqlfmt sql/ --write                                 # 原地写回
seatunnel-agent sqlfmt -d sql/ -F json                              # 机器可读
```

### MCP 工具箱（`seatunnel-agent mcp`）

一个 stdio MCP server 把整套 agent 交给任意 MCP 客户端（Claude Code /
Claude Desktop / Cline / Cursor）：SQL 审查、方言翻译、数据倾斜分析、
变更影响 diff、DataX/Sqoop 迁移，以及基于设置页已保存连接的表结构浏览、
**只读**查询、跨库行数/结构比对（按连接名引用，凭据不进模型上下文）。
所有工具均为确定性实现：内部不调用 LLM、零 token。血缘工具在给出图来源
时加载。设计文档：[`docs/mcp_toolbox.md`](docs/mcp_toolbox.md)

```bash
pip install 'seatunnel-agent[mcp]'
seatunnel-agent mcp                          # 15 个基础工具
seatunnel-agent mcp --no-db                  # 纯静态模式（6 个工具，零数据库面）
seatunnel-agent mcp --connections dev,stage  # 连接白名单
seatunnel-agent mcp --sql-dir sql/           # + 血缘工具与数据字典
seatunnel-agent mcp-stats                    # 工具调用审计统计
claude mcp add seatunnel-agent -- seatunnel-agent mcp   # Claude Code
```

### UI 测试 Agent

驱动真实浏览器的 Gradio 页面自动回归（Playwright + YAML 用例，与 75 项人工
验收清单同编号，支持 LLM 自然语言步骤与模糊断言）：

```bash
python -m seatunnel_agent.ui_testing run --suite smoke --no-llm   # 约 3 分钟,零 token
```

使用文档：[`docs/ui_testing_usage.md`](docs/ui_testing_usage.md)

### 常见问题

| 问题 | 解决方法 |
|------|----------|
| `RuntimeError: API_KEY is not set` | 从 `.env.example` 创建 `.env` 文件并填入 API Key：`cp .env.example .env` |
| `Warning: SeaTunnel binary not found` | 在 `.env` 中设置 `SEATUNNEL_HOME` 为 SeaTunnel 安装路径。仅 `run` 和 `batch` 命令需要安装 SeaTunnel，配置生成、验证、诊断功能不依赖 SeaTunnel。 |
| `429 / Rate limit` 错误 | Agent 会自动指数退避重试（1s → 2s → 4s）。如持续出现，请等待一分钟或切换到限速更高的模型。 |
| `ModuleNotFoundError: No module named 'gradio'` | 安装 UI 依赖：`pip install -e ".[ui]"` |
| `ModuleNotFoundError: No module named 'anthropic'` | 安装对应的 LLM 依赖：`pip install anthropic` 或 `pip install openai`，或全部安装：`pip install -e ".[all]"` |
| Docker 中聊天历史未持久化 | 使用 `docker compose up` —— compose 文件使用命名卷（`agent-history`、`agent-configs`）自动持久化 |

### 许可证

MIT
