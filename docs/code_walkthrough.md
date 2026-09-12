# SeaTunnel Agent 代码思路详解

本文档是对整个项目代码的详细解读，面向正在学习 Agent 开发的读者。读完后你会清楚：每个文件干什么、为什么这样设计、数据怎么流转、核心的 ReAct 循环到底是什么。

---

## 1. 整体架构概览

### 1.1 七个文件的关系

```
用户在终端输入命令
       │
       ▼
   cli.py          ← 入口：解析命令行参数，创建 agent
       │
       ├── config.py    ← 读取 .env，生成 Settings 对象
       │
       ▼
   agent.py         ← 核心：ReAct 循环，调用 Claude API
       │
       ├── prompts.py   ← 生成系统提示词（告诉 Claude 它是谁、能干什么）
       │
       ├── tools.py     ← 定义工具的 JSON Schema + 执行函数
       │
       └── utils.py     ← 通用小工具函数
```

**数据流方向**：

```
cli.py  →  load_settings()  →  SeaTunnelAgent(settings)
                                     │
                                     ▼
                              build_system_prompt()     ← prompts.py
                                     │
                                     ▼
                              client.messages.create()  ← 发送给 Claude API
                                     │
                                     ▼
                              Claude 返回 tool_use      ← Claude 决定调用什么工具
                                     │
                                     ▼
                              execute_tool()            ← tools.py 执行对应函数
                                     │
                                     ▼
                              结果追加到 messages        ← 发回给 Claude
                                     │
                                     ▼
                              Claude 继续推理...         ← 循环，直到 end_turn
```

### 1.2 一句话总结每个文件

| 文件 | 一句话 |
|---|---|
| `__init__.py` | 声明包版本号 |
| `config.py` | 从 `.env` 加载配置，生成不可变的 `Settings` 对象 |
| `utils.py` | 文本截断、日志查找、JSON 安全序列化等小工具 |
| `tools.py` | **两件事**：定义工具的 JSON Schema（给 Claude 看）+ 定义工具的 Python 函数（真正执行） |
| `prompts.py` | 构建系统提示词，包含 SeaTunnel 领域知识和 ReAct 指令 |
| `agent.py` | **项目核心**：ReAct 循环 —— 调 Claude API → 执行工具 → 把结果喂回去 → 循环 |
| `cli.py` | 命令行入口，用 Click 框架定义 `run`、`validate`、`diagnose` 三个子命令 |

---

## 2. 每个文件的详细解读

### 2.1 `__init__.py` — 包声明

```python
"""SeaTunnel Pipeline Builder Agent."""
__version__ = "0.1.0"
```

只做一件事：声明版本号。`cli.py` 会引用这个版本号显示在 `--version` 输出中。

---

### 2.2 `config.py` — 配置管理

**核心思想**：所有配置集中在一个地方管理，其他模块只接收一个 `Settings` 对象，不直接读环境变量。

#### Settings 数据类

```python
@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str
    seatunnel_home: str
    max_retries: int = 3
    model_name: str = "claude-opus-5"
    max_tokens: int = 16000
    seatunnel_bin: str = ""
```

**为什么用 `frozen=True`**：

`frozen=True` 让 Settings 实例创建后不可修改。这是一种防御性编程——配置应该在启动时确定，运行中不应该被意外改变。在测试中也更方便，你可以直接构造 `Settings(...)` 而不用担心某个测试修改了全局状态。

#### load_settings() 函数

```python
def load_settings() -> Settings:
    load_dotenv()                            # 1. 从 .env 文件加载环境变量
    api_key = os.getenv("ANTHROPIC_API_KEY") # 2. 读取每个变量
    if not api_key:
        raise RuntimeError(...)              # 3. 必填项缺失时报错
    ...
    if platform.system() == "Windows":       # 4. 跨平台处理
        bin_name = "seatunnel.cmd"
    else:
        bin_name = "seatunnel.sh"
    ...
    if not Path(seatunnel_bin).exists():     # 5. 二进制不存在时警告（不报错）
        Console(stderr=True).print("[yellow]Warning:...")
    ...
    return Settings(...)                     # 6. 返回不可变对象
```

**设计要点**：
- `load_dotenv()` 来自 `python-dotenv` 库，它把 `.env` 文件里的 `KEY=VALUE` 加载到 `os.environ` 中
- SeaTunnel 二进制不存在时只是警告而不是报错，因为 `validate` 和 `diagnose` 命令不需要 SeaTunnel 安装就能工作
- 跨平台处理：Windows 用 `seatunnel.cmd`，Linux/macOS 用 `seatunnel.sh`

---

### 2.3 `utils.py` — 工具函数

四个小函数，各解决一个具体问题：

#### truncate() — 文本截断

```python
def truncate(text: str, max_chars: int = 3000) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated]"
```

**为什么需要截断**：SeaTunnel 的日志输出可能非常长（几万行），全部喂给 Claude 会浪费 token（=花钱）且可能超出上下文窗口。截断到 3000 字符是一个平衡点——保留足够的错误信息，同时控制成本。

#### safe_json() — 安全序列化

```python
def safe_json(data: Any) -> str:
    try:
        return json.dumps(data, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return json.dumps({"error": "Failed to serialize result"})
```

**为什么需要**：工具函数必须返回字符串（Anthropic API 要求 tool_result 的 content 是字符串）。`safe_json` 确保任何数据都能安全转成 JSON 字符串，即使数据里包含无法序列化的类型（通过 `default=str` 兜底）。

#### resolve_log_path() — 日志路径解析

支持三种输入方式：
- `"auto"` → 自动在 `$SEATUNNEL_HOME/logs/` 下找最新日志
- 一个目录路径 → 找该目录下最新的 `.log` 文件
- 一个文件路径 → 直接使用

这个设计让 Claude 可以传 `"auto"` 来自动定位日志，而不需要知道精确路径。

---

### 2.4 `tools.py` — 工具定义与执行

这是最大的文件，也是理解 Function Calling 的关键。它做两件完全不同但紧密配合的事情：

#### 第一件事：定义工具的 JSON Schema（给 Claude 看）

```python
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "run_seatunnel_job",
        "description": "Execute a SeaTunnel job using the specified config file...",
        "input_schema": {
            "type": "object",
            "properties": {
                "config_path": {
                    "type": "string",
                    "description": "Path to the SeaTunnel HOCON config file",
                },
            },
            "required": ["config_path"],
        },
    },
    # ... 另外 5 个工具定义
]
```

**这些 JSON Schema 的作用**：当你调用 Claude API 时把 `TOOL_DEFINITIONS` 传给 `tools` 参数，Claude 就知道：
- 有哪些工具可用（通过 `name`）
- 每个工具干什么（通过 `description`）
- 调用工具需要什么参数（通过 `input_schema`）

**Claude 不会真的执行这些工具**。它只会说"我想调用 `run_seatunnel_job`，参数是 `{config_path: '/tmp/job.conf'}`"。真正执行是我们代码的事。

`description` 写得好不好直接影响 Claude 的决策质量。比如 `run_seatunnel_job` 的描述里写了 "Call this after creating or fixing a config"，这引导 Claude 在合适的时机使用它。

#### 第二件事：定义工具的 Python 函数（真正执行）

每个工具都有一个对应的 `_` 开头的私有函数：

**`_run_seatunnel_job`** — 最核心的工具

```python
def _run_seatunnel_job(settings: Settings, config_path: str) -> str:
    # 1. 检查 SeaTunnel 二进制是否存在
    if not Path(settings.seatunnel_bin).exists():
        return safe_json({"success": False, "error": "..."})

    # 2. 检查配置文件是否存在
    if not config.exists():
        return safe_json({"success": False, "error": "..."})

    # 3. 用 subprocess 执行 SeaTunnel CLI
    try:
        result = subprocess.run(
            [settings.seatunnel_bin, "--config", str(config.resolve())],
            capture_output=True,   # 捕获 stdout 和 stderr
            text=True,             # 以文本（非字节）返回
            timeout=120,           # 120 秒超时
        )
        return safe_json({
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "stdout": truncate(result.stdout),    # 截断输出
            "stderr": truncate(result.stderr),
        })
    except subprocess.TimeoutExpired:
        return safe_json({"success": False, "error": "timed out"})
```

关键点：
- `subprocess.run` 是 Python 执行外部命令的标准方式，相当于在终端里敲 `seatunnel.sh --config job.conf`
- `capture_output=True` 捕获命令的标准输出和标准错误，这样 Claude 能看到运行结果和报错信息
- `timeout=120` 防止 SeaTunnel 卡死时程序永远等下去
- 返回值里的 `"success"` 字段是给 agent 的 `_track_retry` 方法用的

**`_validate_config`** — 配置验证

```python
def _validate_config(settings: Settings, config_path: str) -> str:
    # 1. 用 pyhocon 解析 HOCON 语法
    config = ConfigFactory.parse_file(str(path))

    # 2. 检查必需的 section 是否存在
    for section in ("env", "source", "transform", "sink"):
        try:
            config[section]
            sections_found.append(section)
        except Exception:
            pass

    # 3. source 和 sink 是必需的，env 和 transform 是可选的
    if "source" not in sections_found:
        errors.append("Missing required 'source' section")
    ...
```

用 `pyhocon` 库做语法级别的检查（它能捕获括号不匹配、格式错误等），再做语义级别的检查（必须有 source 和 sink）。

**`_write_config`** — 写配置（带安全检查）

```python
def _write_config(settings: Settings, config_path: str, content: str) -> str:
    # 安全检查：只允许写入特定扩展名的文件
    if path.suffix not in (".conf", ".hocon", ".config", ".json"):
        return safe_json({"error": "Refusing to write..."})

    # 写入前自动备份
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
    ...
```

两个安全措施：
- 文件扩展名白名单：防止 Claude 误写到不相关的文件（比如系统文件）
- 自动备份：写入前把原文件复制为 `.bak`，出问题可以恢复

#### 调度器（Dispatcher）

```python
_TOOL_MAP = {
    "run_seatunnel_job": _run_seatunnel_job,
    "read_log": _read_log,
    "read_config": _read_config,
    "write_config": _write_config,
    "validate_config": _validate_config,
    "list_connectors": _list_connectors,
}

def execute_tool(tool_name: str, tool_input: dict[str, Any], settings: Settings) -> str:
    fn = _TOOL_MAP.get(tool_name)
    if fn is None:
        return safe_json({"error": f"Unknown tool: {tool_name}"})
    try:
        return fn(settings, **tool_input)
    except Exception as e:
        return safe_json({"error": f"Tool '{tool_name}' failed: {e}"})
```

**这是一个经典的调度器模式**：
- `_TOOL_MAP` 把工具名字映射到函数
- `execute_tool` 根据名字查找函数，用 `**tool_input` 解包参数调用
- 外层 `try/except` 确保任何工具崩溃都不会导致整个 agent 挂掉，而是返回一个错误 JSON 让 Claude 处理

**为什么所有函数签名都是 `(settings, **kwargs) -> str`**：统一签名让调度器代码极其简洁。`settings` 提供路径等配置，`**kwargs` 自动展开 Claude 传入的参数。

---

### 2.5 `prompts.py` — 系统提示词

系统提示词是整个 agent 的"灵魂"——它决定了 Claude 的行为方式。

#### SYSTEM_PROMPT 的结构

提示词分为 6 个部分：

1. **角色定义**："You are a SeaTunnel Pipeline Expert Agent" — 让 Claude 扮演特定角色
2. **ReAct 指令**：明确告诉 Claude 遵循 Think → Act → Observe → Repeat 循环
3. **工具使用指南**：虽然 Claude 已经能看到工具的 JSON Schema，但在系统提示里再次说明"什么时候用什么工具"能显著提高决策质量
4. **SeaTunnel 领域知识**：常用连接器的配置模板——这是你作为领域专家的价值，Claude 本身不一定熟悉每个连接器的参数
5. **错误诊断参考表**：常见报错到修复方案的映射表——这让 Claude 在诊断错误时有明确的方向
6. **行为约束**：最大重试次数、必须先验证再运行等规则

#### build_system_prompt() — 动态拼装

```python
_TASK_HINTS = {
    "run": "The user wants to run a SeaTunnel job...",
    "validate": "The user wants to validate a config file. Do NOT run the job.",
    "diagnose": "The user wants to diagnose errors. Do NOT run or modify anything.",
}

def build_system_prompt(task_type: str, max_retries: int = 3) -> str:
    prompt = SYSTEM_PROMPT.replace("{max_retries}", str(max_retries))
    hint = _TASK_HINTS.get(task_type, "")
    if hint:
        prompt += f"\n## Current Task\n\n{hint}\n"
    return prompt
```

**为什么不用一个固定提示词**：不同命令（run vs validate vs diagnose）需要不同的行为约束。比如 `validate` 命令不应该运行 job，`diagnose` 命令不应该修改文件。通过在提示词末尾追加任务特定的指令，能精确控制 Claude 的行为边界。

`{max_retries}` 是一个简单的模板变量，在运行时替换成实际的配置值。

---

### 2.6 `agent.py` — ReAct 循环（核心）

这是整个项目最重要的文件。先看类结构，再深入循环。

#### 类结构

```python
class SeaTunnelAgent:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        self.messages: list[dict[str, Any]] = []  # 对话历史
        self.retry_count = 0                       # 重试计数器
        self.console = Console()                   # Rich 终端输出
```

- `self.client`：Anthropic SDK 客户端，用来调 Claude API
- `self.messages`：完整的对话历史。这是 ReAct 循环的状态核心——每一轮的对话（用户消息、Claude 回复、工具调用、工具结果）都追加到这里
- `self.retry_count`：专门追踪 `run_seatunnel_job` 的连续失败次数

#### 四个公开入口

```python
def run(self, task: str) -> str:           # 自然语言任务
def run_with_config(self, config_path)     # 运行现有配置
def validate_only(self, config_path)       # 只验证
def diagnose_log(self, log_path)           # 诊断日志
```

它们的结构完全一样：
1. 构建对应的系统提示词（通过 `build_system_prompt(task_type)`）
2. 设置初始用户消息（`self.messages = [{"role": "user", "content": ...}]`）
3. 调用 `self._agent_loop(system)` 进入核心循环

区别只在于系统提示词的 task hint 和初始消息的措辞。

---

### 2.7 `cli.py` — 命令行入口

使用 Click 框架定义三个子命令。

#### Click 框架基础

```python
@click.group()           # 定义命令组（类似 git 有 git push、git pull）
def cli(): ...

@cli.command()           # 在命令组下注册子命令
@click.option(...)       # 定义参数
def run(task, config): ...
```

这让用户可以这样使用：
```bash
seatunnel-agent run --task "..."
seatunnel-agent validate --config job.conf
seatunnel-agent diagnose --log error.log
```

#### _make_agent() — 延迟初始化

```python
def _make_agent():
    from .config import load_settings
    from .agent import SeaTunnelAgent
    settings = load_settings()
    return SeaTunnelAgent(settings)
```

**为什么用函数内导入（lazy import）**：如果在文件顶部导入 `load_settings` 和 `SeaTunnelAgent`，那么执行 `seatunnel-agent --help` 时也会尝试加载配置（读 `.env`），没有 `.env` 就会报错。延迟导入确保只有真正执行命令时才加载这些模块。

#### 错误处理

```python
def _handle_error(e: Exception, verbose: bool) -> None:
    if isinstance(e, anthropic.AuthenticationError):
        console.print("Check your ANTHROPIC_API_KEY")
    elif isinstance(e, anthropic.RateLimitError):
        console.print("Rate limited, wait and retry")
    ...
```

按异常类型提供有针对性的错误信息，而不是打印一堆技术性的堆栈。`--verbose` 标志让高级用户可以看到完整堆栈。

---

## 3. 核心机制：ReAct 循环

### 3.1 什么是 ReAct

ReAct = **Re**asoning + **Act**ing。与普通的"一问一答"LLM 应用不同，ReAct agent 有一个自主决策的循环：

```
普通 LLM 应用：用户提问 → LLM 回答 → 结束

ReAct Agent：
  用户给任务 →
    LLM 思考"我需要先验证配置" →
      调用 validate_config →
        看到"缺少 source 块" →
          LLM 思考"我需要修复配置" →
            调用 write_config →
              LLM 思考"现在可以运行了" →
                调用 run_seatunnel_job →
                  看到运行成功 →
                    LLM 回复"任务完成"
```

关键区别：LLM 自己决定下一步做什么，不是人类写死的 if-else 流程。

### 3.2 _agent_loop 逐行解析

```python
def _agent_loop(self, system_prompt: str) -> str:
    for iteration in range(MAX_LOOP_ITERATIONS):  # 安全上限：最多 20 轮
```

**第 1 步：调用 Claude API**

```python
        response = self.client.messages.create(
            model=self.settings.model_name,       # "claude-opus-5"
            max_tokens=self.settings.max_tokens,   # 16000
            system=system_prompt,                  # 系统提示词
            tools=TOOL_DEFINITIONS,                # 6 个工具的 JSON Schema
            messages=self.messages,                # 完整对话历史
            thinking={"type": "adaptive"},         # 自适应思维
        )
```

**`messages` 里有什么？**

第一轮：
```json
[{"role": "user", "content": "把 MySQL 的 users 表同步到 Console"}]
```

第二轮（假设第一轮 Claude 调用了 validate_config）：
```json
[
  {"role": "user", "content": "把 MySQL 的 users 表同步到 Console"},
  {"role": "assistant", "content": [TextBlock("让我先验证配置"), ToolUseBlock("validate_config", {...})]},
  {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "...", "content": "{\"valid\": true}"}]}
]
```

每一轮都把完整历史发给 Claude，所以 Claude 始终能看到之前所有的操作和结果。

**第 2 步：处理 Claude 的回复**

```python
        assistant_content = response.content
        # response.content 是一个列表，可能包含多种类型的 block：
        # - ThinkingBlock: Claude 的推理过程
        # - TextBlock: Claude 对用户说的话
        # - ToolUseBlock: Claude 想调用的工具

        self.messages.append({"role": "assistant", "content": assistant_content})
```

**必须把完整的 `response.content` 追加到 messages 里**，不能只留文本。因为 Anthropic API 要求对话历史里的 `tool_use` block 必须和后续的 `tool_result` 配对。如果你只存了文本，后面的 tool_result 找不到对应的 tool_use_id，API 会报错。

**第 3 步：检查是否结束**

```python
        if response.stop_reason == "end_turn":
            return self._extract_text(assistant_content)
```

`stop_reason` 有几种可能：
- `"end_turn"`: Claude 认为任务完成了，不再调用工具 → 退出循环
- `"tool_use"`: Claude 想调用一个或多个工具 → 继续循环
- `"max_tokens"`: 输出被截断了 → 也退出（可能需要处理）

**第 4 步：执行工具调用**

```python
        tool_results = []
        for block in assistant_content:
            if block.type == "tool_use":
                # block.name = "validate_config"
                # block.input = {"config_path": "/tmp/job.conf"}
                # block.id = "toolu_01ABC..."  （API 生成的唯一 ID）

                result = execute_tool(block.name, block.input, self.settings)
                # result 是一个 JSON 字符串，比如：
                # '{"valid": true, "errors": [], "warnings": [...]}'

                if block.name == "run_seatunnel_job":
                    self._track_retry(result)  # 只追踪运行任务的成败

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,   # 必须和 tool_use 的 id 对应
                    "content": result,
                })
```

**为什么 tool_use_id 很重要**：Claude 一次可能调用多个工具（并行工具调用），每个结果必须通过 `tool_use_id` 关联到对应的调用。

**第 5 步：把结果喂回去**

```python
        self.messages.append({"role": "user", "content": tool_results})
```

工具结果以 `"role": "user"` 的消息追加。这是 Anthropic API 的约定——虽然不是用户说的话，但在 API 协议层面，工具结果放在 user 消息里。

**第 6 步：检查重试限制**

```python
        if self.retry_count >= self.settings.max_retries:
            self.messages.append({
                "role": "user",
                "content": "SYSTEM: Maximum retry limit (3) reached. "
                           "Please summarize what you tried and suggest manual fixes."
            })
```

当连续失败次数达到上限时，注入一条系统消息告诉 Claude "别再试了，总结一下吧"。Claude 看到这个消息后通常会在下一轮给出总结性回复（`stop_reason = "end_turn"`）。

### 3.3 重试追踪机制

```python
def _track_retry(self, result: str) -> None:
    data = json.loads(result)
    if data.get("success"):
        self.retry_count = 0      # 成功了→重置计数器
    else:
        self.retry_count += 1     # 失败了→计数器 +1
```

**只追踪 `run_seatunnel_job`**，因为其他工具（读配置、验证、读日志）的"失败"不算真正的重试——它们只是信息收集步骤。只有"运行 job 失败 → 修改 → 再运行"才算一次重试。

**成功时重置**：如果 agent 修了一个错又遇到另一个错，计数器从 0 重新开始，因为新的错误是一个新的问题。

---

## 4. 核心机制：Tool Calling

### 4.1 两个平行的数据结构

Function Calling 的核心概念是：**你需要维护两套对应的东西**。

**第一套：JSON Schema（声明层）**
```python
TOOL_DEFINITIONS = [
    {
        "name": "validate_config",         # 名字
        "description": "Validate a ...",   # 描述（Claude 看这个决定要不要用）
        "input_schema": {                  # 参数格式
            "type": "object",
            "properties": {
                "config_path": {"type": "string", "description": "..."},
            },
            "required": ["config_path"],
        },
    },
]
```
这是告诉 Claude "你有这些工具可以用，参数长这样"。Claude 会根据任务需要和描述来决定调用哪个。

**第二套：Python 函数（执行层）**
```python
def _validate_config(settings: Settings, config_path: str) -> str:
    # 真正干活的代码
    config = ConfigFactory.parse_file(config_path)
    ...
```
这是真正执行工具的代码。Claude 不会执行它——Claude 只说"我要调 validate_config，参数是 `/tmp/job.conf`"，然后我们的代码调用这个函数。

### 4.2 调度器连接两套结构

```python
_TOOL_MAP = {
    "validate_config": _validate_config,
    "run_seatunnel_job": _run_seatunnel_job,
    ...
}

def execute_tool(tool_name, tool_input, settings):
    fn = _TOOL_MAP[tool_name]           # 通过名字找到函数
    return fn(settings, **tool_input)   # 调用函数
```

**`**tool_input` 解包**：Claude 返回 `{"config_path": "/tmp/job.conf"}`，Python 的 `**` 操作符把它展开为 `config_path="/tmp/job.conf"` 传给函数。这要求 JSON Schema 里的参数名和 Python 函数的参数名完全一致。

### 4.3 完整调用链路（一次工具调用）

```
1. agent.py 调用 client.messages.create(tools=TOOL_DEFINITIONS, messages=...)
          ↓
2. Claude API 返回 response，其中 response.content 包含：
   [TextBlock("我来验证一下配置"), ToolUseBlock(name="validate_config", input={"config_path": "..."})]
          ↓
3. agent.py 遍历 response.content，发现 ToolUseBlock
          ↓
4. agent.py 调用 execute_tool("validate_config", {"config_path": "..."}, settings)
          ↓
5. tools.py 的调度器在 _TOOL_MAP 里找到 _validate_config 函数
          ↓
6. _validate_config 用 pyhocon 解析文件，返回 JSON 字符串
          ↓
7. agent.py 把结果包装成 tool_result，追加到 messages
          ↓
8. 回到步骤 1，带着更新后的 messages 再次调用 Claude API
```

---

## 5. 完整调用链路

用户执行 `seatunnel-agent run --task "把 FakeSource 的数据打印到控制台"` 时，完整流程：

### 第一阶段：命令解析（cli.py）

```
1. Click 框架解析命令行参数
   → task = "把 FakeSource 的数据打印到控制台"
   → config = None

2. _make_agent() 被调用
   → load_settings() 读取 .env 文件
   → 创建 Settings 对象（包含 API key、SeaTunnel 路径等）
   → 创建 SeaTunnelAgent(settings)
     → 内部创建 anthropic.Anthropic 客户端

3. agent.run(task) 被调用
```

### 第二阶段：Agent 初始化（agent.py）

```
4. build_system_prompt("run", max_retries=3)
   → 生成完整的系统提示词，包含 SeaTunnel 知识 + ReAct 指令
   → 末尾追加 task hint: "如果用户给了自然语言描述，先生成配置"

5. self.messages = [{"role": "user", "content": "把 FakeSource 的数据打印到控制台"}]

6. 进入 _agent_loop(system_prompt)
```

### 第三阶段：ReAct 循环（agent.py ↔ Claude API ↔ tools.py）

**第 1 轮**：

```
7. 调用 Claude API（带系统提示词 + 工具定义 + 对话历史）

8. Claude 返回（思维链 + 文本 + 工具调用）：
   ThinkingBlock: "用户想要 FakeSource 到 Console，让我先写一个配置文件"
   TextBlock: "我来为你创建一个 SeaTunnel 配置"
   ToolUseBlock: write_config({
     config_path: "fake_to_console.conf",
     content: "env { ... } source { FakeSource { ... } } sink { Console {} }"
   })

9. execute_tool("write_config", {...}, settings)
   → _write_config 写入文件，返回 {"success": true}

10. tool_result 追加到 messages
```

**第 2 轮**：

```
11. 再次调用 Claude API（messages 现在包含了第 1 轮的全部历史）

12. Claude 返回：
    ThinkingBlock: "配置写好了，我应该先验证再运行"
    ToolUseBlock: validate_config({config_path: "fake_to_console.conf"})

13. execute_tool("validate_config", {...}, settings)
    → _validate_config 用 pyhocon 解析，返回 {"valid": true, ...}

14. tool_result 追加到 messages
```

**第 3 轮**：

```
15. 再次调用 Claude API

16. Claude 返回：
    ThinkingBlock: "配置有效，现在运行 job"
    ToolUseBlock: run_seatunnel_job({config_path: "fake_to_console.conf"})

17. execute_tool("run_seatunnel_job", {...}, settings)
    → subprocess.run 执行 SeaTunnel CLI
    → 返回 {"success": true, "stdout": "...", "stderr": ""}

18. _track_retry(result) → success=true → retry_count 重置为 0
```

**第 4 轮**：

```
19. 再次调用 Claude API

20. Claude 返回：
    TextBlock: "任务完成！配置文件已创建，job 运行成功，FakeSource 生成了 10 行数据。"
    stop_reason = "end_turn"

21. _agent_loop 返回文本结果
```

### 第四阶段：输出结果（cli.py）

```
22. console.print(f"Final result:\n{result}")
    → 用 Rich 格式化输出最终结果给用户
```

---

## 6. 关键设计决策

### 6.1 为什么用手动循环而不是 Tool Runner

Anthropic SDK 提供了 `client.beta.messages.tool_runner()`，它能自动处理整个工具调用循环。但本项目选择手动写循环，原因：

1. **学习目的**：作为一个学习 agent 开发的项目，手写循环能让你理解每一步发生了什么——消息格式、工具调用协议、对话历史管理。用 Tool Runner 会把这些细节隐藏掉。

2. **重试计数**：我们需要单独追踪 `run_seatunnel_job` 的失败次数（而非所有工具调用），并在达到上限时注入特殊消息。Tool Runner 的钩子虽然能做到，但代码会更复杂。

3. **实时状态展示**：我们在每次工具调用前后都用 Rich 打印状态。手动循环让展示逻辑很自然地嵌入循环体中。

### 6.2 为什么用 adaptive thinking

```python
thinking={"type": "adaptive"}
```

而不是 `{"type": "enabled", "budget_tokens": N}`：

- `adaptive` 让 Claude 自己决定需要多少推理。简单操作（读个文件）几乎不思考，复杂诊断（分析一个 20 行的 Java 堆栈）会深入推理。
- `budget_tokens` 是固定的，设少了复杂任务推理不够，设多了简单任务浪费 token。
- 在新版 Claude 模型上（Opus 5 等），`budget_tokens` 已经被移除，只能用 `adaptive`。

### 6.3 为什么要截断工具返回

SeaTunnel 一个 job 的 stderr 可能有上万行 Java 堆栈追踪。全部发给 Claude 的问题：
- **成本**：每个 token 都要花钱。10000 行日志 ≈ 30000+ token，一次调用可能花好几美元。
- **上下文窗口**：虽然 Claude 有 1M context，但每轮都发完整历史，过长的工具结果会很快吃满。
- **质量**：太多噪音反而降低 Claude 的诊断质量。通常错误信息在日志末尾，3000 字符足够。

### 6.4 为什么写配置前要备份

```python
if path.exists():
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
```

Claude 生成的配置可能有问题。如果直接覆盖了用户的原始配置，用户就丢了一个可能能用的版本。自动备份确保用户随时可以恢复。这也体现在系统提示词里（"Always back up configs before modifying"），但代码层面做了强制保证。

### 6.5 为什么工具函数永远返回字符串而不抛异常

```python
def execute_tool(...) -> str:
    try:
        return fn(settings, **tool_input)
    except Exception as e:
        return safe_json({"error": f"Tool failed: {e}"})
```

如果工具抛异常，整个 agent 循环就中断了。用户看到的是一个 Python 错误，而不是 Claude 的诊断。通过把所有异常转换成错误 JSON 返回给 Claude，让 Claude 来决定怎么处理——它可能会换一种方式重试，或者告诉用户"这个操作失败了，原因是..."。

这是 agent 开发的一个重要模式：**把错误当数据传给 LLM，而不是让程序崩溃**。
