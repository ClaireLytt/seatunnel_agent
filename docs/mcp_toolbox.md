# MCP 工具箱设计（`seatunnel-agent mcp`）

把整个 agent 套件以**一个 stdio MCP server** 暴露给任意 MCP 客户端
（Claude Code / Claude Desktop / Cline / Cursor），让外部 AI 直接获得
大数据 SQL 工程能力。方向定位：**被集成**——本仓库的确定性能力做工具，
调用方的 LLM 做大脑。

## 设计原则

1. **只暴露确定性能力。** 工具内部一律不调用 LLM：调用方本身就是
   LLM，再嵌一层既烧钱又不可复现。静态审查 / 方言翻译 / 倾斜扫描 /
   变更影响 / 配置迁移都是纯函数，零 token、同输入同输出。
2. **凭据不进模型上下文。** 数据库工具只接受**连接名**（Web 界面
   `/settings` 维护的加密预设，与数据比对页共用一套
   `ConnectionPresetsStore`）；密码永远不出现在工具参数、模型输入或
   工具返回里。
3. **只读执行。** `run_query` 复用数据倾斜一致性实测的守卫
   `extract_single_select`：仅单条 SELECT/WITH（允许前导 SET，但会被
   丢弃不执行），多语句和任何写操作直接拒绝；行数硬上限 500。
4. **错误即文本。** 工具永不抛异常——返回可读的中英文错误消息，MCP
   客户端两种情况下展示的都是文本，堆栈只会污染上下文。
5. **工具函数与 mcp 包解耦。** `build_tool_functions()` 返回普通
   callable（无 mcp 依赖即可单测），`create_mcp_server()` 只做 FastMCP
   接线——与 `lineage-mcp` / `skew-mcp` 同一模式。

## 工具清单

### 纯静态分析（永远可用，零依赖）

| 工具 | 说明 | 底层 |
|---|---|---|
| `sql_review(sql, dialect, ddl?, lang?)` | 静态规则审查，严重度分级报告；ddl 可选启用 schema 校验 | `sql_review.static_review_report` |
| `sql_transpile(sql, to_dialect, from_dialect?, lang?)` | 方言翻译 + 不兼容点清单；源方言可自动推断 | `sql_transpile.translate` |
| `skew_check(sql, dialect?, lang?)` / `skew_check_file(path, ...)` | 数据倾斜静态分析（DS001–DS013） | `data_skew`（复用其 MCP 工厂） |
| `impact_diff(old_sql, new_sql, dialect?, lang?)` | 两段 SQL 的变更影响面（表/字段级 diff + 严重度） | `data_lineage.analyze_sql_texts` |
| `migrate_to_seatunnel(content, source_kind?, lang?)` | DataX JSON / sqoop 命令 → SeaTunnel HOCON + 迁移说明；kind 默认 auto（`{` 开头判 DataX） | `config_migrate` |

### 数据库工具（按名引用已保存连接）

| 工具 | 说明 |
|---|---|
| `list_saved_connections()` | 列出连接名/类型/host/库（不含凭据） |
| `list_tables(connection, keyword?)` | 表名列表，子串过滤，上限 200 |
| `table_schema(connection, table)` | 列名/类型/注释 + 分区列 |
| `run_query(connection, sql, max_rows?)` | **只读**查询，单条 SELECT/WITH，≤500 行 |
| `compare_row_count(conn_a, conn_b, table_a, table_b?, where?)` | 跨库行数比对（where 同时作用两侧，禁分号） |
| `compare_schema(conn_a, conn_b, table_a, table_b?)` | 跨库结构比对：单侧独有列 + 同名列类型差异 |

连接按名缓存 executor（每个 server 进程一份），首次使用时
`test_connection` 校验。

### 血缘工具（可选，需给图来源）

启动时给出 `--sql-dir` / `--seatunnel-dir` / `--hive` 之一才加载，
完整复用 `lineage-mcp` 的工具集（上下游链路、最短路径、SLA 影响、
治理体检等）。

## 启动与客户端配置

```bash
pip install 'seatunnel-agent[mcp]'
seatunnel-agent mcp                          # 基础工具箱
seatunnel-agent mcp --sql-dir sql/ --lang en # + 血缘工具
```

Claude Code：

```bash
claude mcp add seatunnel-agent -- seatunnel-agent mcp --sql-dir sql/
```

Claude Desktop（`claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "seatunnel-agent": {
      "command": "seatunnel-agent",
      "args": ["mcp", "--sql-dir", "D:/warehouse/sql"]
    }
  }
}
```

## 与既有入口的关系

- `lineage-mcp` / `skew-mcp` 保留（单一职责、更小攻击面），`mcp` 是
  聚合入口；三者共用同一批工具函数，不存在两份实现。
- REST（`/api/...`）面向服务间调用，MCP 面向 AI 客户端；同一批纯函数
  的两种传输层。
- 倾斜工具照旧写入分析历史（`source=mcp`），`skew-stats` 可见。

## 扩展约定

新 agent 想进工具箱：在自己包里提供
`build_tool_functions() -> dict[str, Callable[..., str]]`（返回字符串、
错误不抛异常、docstring 即工具说明书），在 `mcp_toolbox.py` 里
`tools.update(...)` 一行接入；涉及 LLM 或写操作的能力**不进默认工具箱**，
要么留在页面/CLI，要么以显式 opt-in 开关单独讨论。
