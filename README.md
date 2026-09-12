# SeaTunnel Pipeline Builder Agent

> AI-powered Apache SeaTunnel pipeline builder — describe your data task in natural language, and the Agent generates configs, runs jobs, diagnoses errors, and fixes them automatically.

[English](#english) | [中文](#中文)

---

<a id="english"></a>

## English

### Features

- **Natural Language → Pipeline Config**: Describe what you need ("sync MySQL users to Console"), get a working HOCON config
- **Auto-Diagnose & Fix**: When a job fails, the Agent reads the log, identifies the root cause, patches the config, and retries
- **Config Validation**: Check any `.conf` file for syntax errors and missing sections without running the job
- **Log Diagnosis**: Point the Agent at a SeaTunnel log file and get a structured root-cause analysis
- **Config Template Library**: 6 built-in templates (FakeSource, MySQL-CDC, Jdbc, Kafka, LocalFile) — select a template and the Agent fills in parameters
- **Connection Testing**: Test TCP connectivity to databases/services before generating configs, avoiding config-then-fail cycles
- **Connector Documentation Query**: Look up connector parameters (types, required/optional, examples) for 11 connectors before writing configs — reduces hallucination and config errors
- **Job Run Metrics**: Automatically parses SeaTunnel job output to display structured metrics (rows read/written, bytes, duration, status)
- **Config Version History**: Every `write_config` call saves a timestamped version; browse and compare past versions of any config file
- **Batch Task Management**: Run multiple pipeline configs sequentially with per-job results and pass/fail summary; stops on first failure by default
- **Multi-Turn Session Memory**: Agent remembers configs, job results, and connection tests across turns — say "run it again" and it knows which config
- **Config Diff Display**: When overwriting an existing config, the UI shows a unified diff of what changed
- **Task Progress Visualization**: Real-time step counter and streaming text output with cursor indicator
- **Export to ZIP**: Download a session report (Markdown) + all generated config files as a ZIP archive
- **Stop Button**: Interrupt a running agent at any time
- **Web UI**: Real-time chat interface showing the Agent's thinking, tool calls, and results — with bilingual support (English / Chinese)
- **Dark Mode**: Automatically adapts to system dark/light preference
- **Multi-LLM Support**: Works with Claude, GPT-4o, DeepSeek, Kimi/Moonshot, Qwen, GLM, and any OpenAI-compatible API
- **Demo Mode**: Try the full Agent workflow without an API key

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
│  STATUS      │  │ [Message input] [Demo] [■] [Send]│   │
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

# Validate a config file
seatunnel-agent validate --config examples/fake_to_console.conf

# Diagnose a log file
seatunnel-agent diagnose --log /path/to/seatunnel.log

# Verbose output
seatunnel-agent -v run --task "..."
```

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
    ▼
┌──────────────────────────────────────┐
│           SeaTunnel Agent            │
│                                      │
│   ┌──────────┐    ┌───────────────┐  │
│   │   LLM    │◄──►│ System Prompt │  │
│   │  Client  │    │  + Session    │  │
│   │(multi-   │    │    Context    │  │
│   │ provider)│    └───────────────┘  │
│   └────┬─────┘                       │
│        │                             │
│   ┌────▼─────┐                       │
│   │  ReAct   │  Think → Act →        │
│   │  Loop    │  Observe → Repeat     │
│   └────┬─────┘                       │
│        │                             │
│   ┌────▼─────────────────────────┐   │
│   │        12 Tools              │   │
│   │  run_seatunnel_job           │   │
│   │  read_config / write_config  │   │
│   │  validate_config             │   │
│   │  read_log / list_connectors  │   │
│   │  test_connection             │   │
│   │  list_templates / use_template│  │
│   │  query_connector_docs        │   │
│   │  list_config_versions        │   │
│   │  run_batch                   │   │
│   └──────────────────────────────┘   │
└──────────────────────────────────────┘
    │
    ▼
Apache SeaTunnel (Data Integration Engine)
```

### Project Structure

```
seatunnel_agent/
├── pyproject.toml              # Project config & dependencies
├── .env.example                # Environment variable template
├── src/seatunnel_agent/
│   ├── config.py               # Config loading (.env → Settings)
│   ├── llm.py                  # Multi-provider LLM abstraction
│   ├── utils.py                # Utility functions
│   ├── tools.py                # 12 tool definitions + executor
│   ├── templates.py            # Built-in pipeline config templates
│   ├── connector_docs.py       # Connector parameter documentation (11 connectors)
│   ├── prompts.py              # System prompt (SeaTunnel domain knowledge)
│   ├── agent.py                # ReAct loop + session context tracking
│   ├── history.py              # Chat session persistence
│   ├── cli.py                  # Click CLI entry point
│   └── ui.py                   # Gradio Web UI (bilingual, dark mode)
├── tests/                      # 233 unit tests
│   ├── test_config.py          # Settings & env loading
│   ├── test_tools.py           # All 12 tools, metrics parser, version history, batch
│   ├── test_templates.py       # Template registry, rendering, tool integration
│   ├── test_connector_docs.py  # Connector documentation query & lookup
│   ├── test_agent.py           # ReAct loop, context tracking, entry points
│   ├── test_history.py         # Session persistence, agent context roundtrip
│   ├── test_llm.py             # LLM client (Anthropic + OpenAI providers)
│   ├── test_prompts.py         # System prompt, task hints, tool references
│   ├── test_ui_format.py       # Event formatting, export, normalize, EventCollector
│   ├── test_utils.py           # Utility functions (truncate, log resolution)
│   └── test_cli.py             # CLI commands & help text
└── examples/                   # Example configs
    ├── fake_to_console.conf
    └── mysql_to_console.conf
```

### Testing

```bash
# Run all 233 tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_agent.py -v

# Run with coverage
pytest tests/ --cov=seatunnel_agent --cov-report=term-missing
```

Test coverage by module:

| Module | Tests | Coverage |
|--------|-------|----------|
| `config.py` | 10 | Settings loading, env vars, provider validation |
| `tools.py` | 38 | All 12 tools, path traversal security, diff, metrics parser, version history, batch |
| `templates.py` | 10 | Template registry, rendering, tool integration |
| `connector_docs.py` | 13 | Connector query, param detail, case-insensitive lookup, type validation |
| `agent.py` | 22 | ReAct loop, context tracking (all 12 tools), retry logic, entry points |
| `history.py` | 19 | Save/load, rename, delete, agent context roundtrip, msg count |
| `llm.py` | 15 | Anthropic & OpenAI clients, tool result formatting |
| `prompts.py` | 11 | System prompt content, task hints, tool references |
| `ui.py` | 34 | Event formatting, export, TextMessage normalization, EventCollector, new tool rendering |
| `utils.py` | 13 | truncate, find_latest_log, safe_json, resolve_log_path |
| `cli.py` | 7 | CLI commands and help text |

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
- **配置模板库**：内置 6 个常用模板（FakeSource、MySQL-CDC、Jdbc、Kafka、LocalFile），选择模板后 Agent 自动填充参数
- **连接测试**：生成配置前先测试数据库/服务的 TCP 连通性，避免写完配置才发现连不上
- **连接器文档查询**：查询 11 个连接器的参数文档（类型、必填/可选、示例值），在生成配置前确认正确的参数名和格式，减少幻觉和配置错误
- **作业运行指标**：自动解析 SeaTunnel 作业输出，结构化展示运行指标（读取/写入行数、字节数、耗时、状态）
- **配置版本历史**：每次 `write_config` 自动保存带时间戳的版本；可以浏览和比较任何配置文件的历史版本
- **批量任务管理**：顺序执行多个管道配置，返回每个作业的结果和通过/失败汇总；默认遇到第一个失败即停止
- **多轮会话记忆**：Agent 记住本次会话的配置路径、执行结果和连接测试，说"运行刚才的配置"就能直接执行
- **配置 Diff 展示**：覆盖已有配置时，UI 展示新旧配置的 unified diff
- **任务进度可视化**：实时显示步骤计数和流式文本输出（带光标指示符）
- **导出 ZIP**：下载会话报告（Markdown）+ 所有生成的配置文件
- **停止按钮**：随时中断正在运行的 Agent
- **Web UI**：实时聊天界面，展示 Agent 的思考过程、工具调用和结果 —— 支持中英文双语
- **暗色模式**：自动适配系统暗色/亮色主题
- **多模型支持**：Claude、GPT-4o、DeepSeek、Kimi/Moonshot、通义千问、智谱 GLM，以及任何兼容 OpenAI API 的模型
- **演示模式**：无需 API Key 即可体验完整的 Agent 工作流程

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
│  [连接]      │  │ [输入框]        [演示] [■] [发送]│   │
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

# 验证配置文件
seatunnel-agent validate --config examples/fake_to_console.conf

# 诊断日志
seatunnel-agent diagnose --log /path/to/seatunnel.log

# 详细输出
seatunnel-agent -v run --task "..."
```

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
    ▼
┌──────────────────────────────────────┐
│           SeaTunnel Agent            │
│                                      │
│   ┌──────────┐    ┌───────────────┐  │
│   │   LLM    │◄──►│ System Prompt │  │
│   │  Client  │    │  + 会话上下文  │  │
│   │ (多模型)  │    └───────────────┘  │
│   └────┬─────┘                       │
│        │                             │
│   ┌────▼─────┐                       │
│   │  ReAct   │  Think → Act →        │
│   │  Loop    │  Observe → Repeat     │
│   └────┬─────┘                       │
│        │                             │
│   ┌────▼─────────────────────────┐   │
│   │        12 个工具              │   │
│   │  run_seatunnel_job           │   │
│   │  read_config / write_config  │   │
│   │  validate_config             │   │
│   │  read_log / list_connectors  │   │
│   │  test_connection             │   │
│   │  list_templates / use_template│  │
│   │  query_connector_docs        │   │
│   │  list_config_versions        │   │
│   │  run_batch                   │   │
│   └──────────────────────────────┘   │
└──────────────────────────────────────┘
    │
    ▼
Apache SeaTunnel（数据集成引擎）
```

### 项目结构

```
seatunnel_agent/
├── pyproject.toml              # 项目配置与依赖
├── .env.example                # 环境变量模板
├── src/seatunnel_agent/
│   ├── config.py               # 配置加载（.env → Settings）
│   ├── llm.py                  # 多模型 LLM 抽象层
│   ├── utils.py                # 工具函数
│   ├── tools.py                # 12 个工具定义 + 执行器
│   ├── templates.py            # 内置管道配置模板库
│   ├── connector_docs.py       # 连接器参数文档（11 个连接器）
│   ├── prompts.py              # System Prompt（SeaTunnel 领域知识）
│   ├── agent.py                # ReAct 循环 + 会话上下文追踪
│   ├── history.py              # 对话历史持久化
│   ├── cli.py                  # Click CLI 入口
│   └── ui.py                   # Gradio Web UI（中英双语，暗色模式）
├── tests/                      # 233 个单元测试
│   ├── test_config.py          # Settings 与环境变量
│   ├── test_tools.py           # 12 个工具、路径安全、指标解析、版本历史、批量任务
│   ├── test_templates.py       # 模板注册、渲染、工具集成
│   ├── test_connector_docs.py  # 连接器文档查询与查找
│   ├── test_agent.py           # ReAct 循环、上下文追踪（12 个工具）、重试逻辑、入口函数
│   ├── test_history.py         # 会话持久化、上下文字段
│   ├── test_llm.py             # LLM 客户端（Anthropic + OpenAI）
│   ├── test_prompts.py         # System Prompt 内容验证
│   ├── test_ui_format.py       # 事件格式化、导出、TextMessage 处理、EventCollector、新工具渲染
│   ├── test_utils.py           # 工具函数（truncate、日志解析）
│   └── test_cli.py             # CLI 命令与帮助文本
└── examples/                   # 示例配置
    ├── fake_to_console.conf
    └── mysql_to_console.conf
```

### 测试

```bash
# 运行全部 233 个测试
pytest tests/ -v

# 运行特定测试文件
pytest tests/test_agent.py -v

# 生成覆盖率报告
pytest tests/ --cov=seatunnel_agent --cov-report=term-missing
```

各模块测试覆盖：

| 模块 | 测试数 | 覆盖范围 |
|------|--------|----------|
| `config.py` | 10 | Settings 加载、环境变量、Provider 验证 |
| `tools.py` | 38 | 全部 12 个工具、路径安全、Diff 生成、指标解析、版本历史、批量任务 |
| `templates.py` | 10 | 模板注册、渲染、工具集成 |
| `connector_docs.py` | 13 | 连接器查询、参数详情、大小写无关查找、类型验证 |
| `agent.py` | 22 | ReAct 循环、上下文追踪（12 个工具）、重试逻辑、入口函数 |
| `history.py` | 19 | 保存/加载、重命名、删除、上下文字段、消息计数 |
| `llm.py` | 15 | Anthropic 与 OpenAI 客户端、工具结果格式化 |
| `prompts.py` | 11 | System Prompt 内容、任务提示、工具引用 |
| `ui.py` | 34 | 事件格式化、导出、TextMessage 标准化、EventCollector、新工具渲染 |
| `utils.py` | 13 | truncate、find_latest_log、safe_json、resolve_log_path |
| `cli.py` | 7 | CLI 命令和帮助文本 |

### 许可证

MIT
