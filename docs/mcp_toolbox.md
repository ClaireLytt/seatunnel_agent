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
| `compare_checksum(conn_a, conn_b, table_a, table_b?, where?)` | 分段校验和比对（同名列交集逐段哈希），结构/行数一致后定位内容差异 |
| `skew_verify(connection, sql, dialect?, sample_pct?)` | **实测验证倾斜**：只读 GROUP BY 探针测真实键值分布，返回确认/热点值/引擎参数/按实测值生成的改写模板 |
| `compare_query_results(connection, sql_a, sql_b)` | 一致性实测：两版 SQL 结果等价性（行数 → 逐行多重集 → 逐列聚合指纹），验证改写/迁移 |

`run_query` 在支持 LIMIT 的引擎上会把查询包成
`SELECT * FROM (q) mcp_q LIMIT n` —— 取数上限之外再加**引擎侧上限**，
大表不做全量计算；不支持 LIMIT 的引擎回落为仅取数上限。

连接按名缓存 executor（每个 server 进程一份），首次使用时
`test_connection` 校验。

### 血缘工具（可选，需给图来源）

启动时给出 `--sql-dir` / `--seatunnel-dir` / `--hive` 之一才加载，
完整复用 `lineage-mcp` 的工具集（上下游链路、最短路径、SLA 影响、
治理体检等），另加 `data_dictionary()`（从血缘图生成分层数据字典，
不连接数据库）。

## 部署安全开关

- `--no-db`：纯静态模式，只暴露 6 个静态分析工具——把工具箱交给不受控的
  AI 时的零数据库攻击面选项。
- `--connections dev,stage`：连接白名单，数据库工具只能使用列出的连接名
  （`list_saved_connections` 同样只列白名单内的）。
- 查询超时：连库调用带硬超时（默认 60s，`SEATUNNEL_MCP_QUERY_TIMEOUT`
  可调）——挂住的查询不会永久阻塞 MCP 客户端，超时同时重置该连接缓存。
- 失效连接自愈：任何查询失败都会丢弃缓存的 executor，下次调用自动重连
  ——数据库重启不需要重启 MCP server。

## 审计与信任

- **审计日志**：每次工具调用记一行 `logs/mcp_toolbox.jsonl`
  （时间/工具/参数摘要 ≤400 字符/是否成功/耗时；`SEATUNNEL_MCP_AUDIT_PATH`
  可重定向，10 MB 轮转，best-effort 永不阻断调用）。AI 客户端在真实
  数据库上做了什么，事后可查。
- **工具注解**：全部工具标注 `readOnlyHint=true / destructiveHint=false`；
  纯静态工具另标 `idempotentHint=true`（连库工具的结果随数据变化，不标）。
  支持注解的 MCP 客户端据此展示信任级别。
- **异常兜底**：审计包装层把任何未捕获异常转成 `内部错误: ...` 文本，
  协议层永远收到正常结果而非 tool error。

## Prompts（内置工作流）

支持 prompts 的客户端可直接触发两个多工具编排模板：

- `skew_tuning_workflow(sql, connection?)` —— 静态扫描 → 实测验证 →
  按热点值改写 → 一致性验收。
- `migration_acceptance_workflow(connection_a, connection_b, table)` ——
  结构 → 行数 → 校验和三级验收，任一级不一致即停下分析。

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

## Resources（免工具调用的目录浏览）

- `seatunnel://rules/data-skew` —— DS001–DS013 规则目录
- `seatunnel://rules/sql-review` —— 审查规则类别目录
- `seatunnel://dialects` —— 各工具支持的方言
- `seatunnel://connections` —— 已保存连接（不含凭据；`--no-db` 时不注册）

## 发布到 registry

产品化清单（server 已带 `version` 元数据，随包版本走）：

0. 仓库根的 `server.json` 是可提交的注册清单（2025-10-17 schema，
   `registryType: pypi` + stdio），README 已带 `mcp-name` 归属校验标记；
   前置条件是包先发上 PyPI，之后 `mcp-publisher login github && mcp-publisher publish`。
1. `pip install seatunnel-agent[mcp]` 可直接安装（extra 已在 pyproject 定义）。
2. stdio 启动命令即 `seatunnel-agent mcp`，无额外配置也能起 15 个基础工具。
3. 发布物料：本文档的工具清单表 + README 双语章节；registry 条目建议
   描述词用 "big-data SQL toolbox: review / transpile / skew / lineage /
   migration / cross-db compare"。
4. CI 冒烟（tests.yml）在最新 mcp SDK 上启动 server 并 `list_tools`，
   防 SDK 改名（FastMCP→MCPServer 已发生过一次，由 `mcp_compat.py` 兜底）。

## 扩展约定

新 agent 想进工具箱：在自己包里提供
`build_tool_functions() -> dict[str, Callable[..., str]]`（返回字符串、
错误不抛异常、docstring 即工具说明书），在 `mcp_toolbox.py` 里
`tools.update(...)` 一行接入；涉及 LLM 或写操作的能力**不进默认工具箱**，
要么留在页面/CLI，要么以显式 opt-in 开关单独讨论。
