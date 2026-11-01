# Agent 工厂配方

新开一个数据 agent 的完整路径。机械面交给脚手架,设计面按下列骨架手写。

## 0. 脚手架（一条命令）

```
python scripts/new_agent.py <name> --route /<slug> --page-title "Title"
```

产出:前端 workspace（从捐赠 agent 复制并改路由,默认 topic_schema）、
frontend/package.json 注册、tests/test_<slug>_page.py 的
standard_page_tests spec（含 `<TODO>` 待填位）。

## 1. 后端包 src/seatunnel_agent/agents/data/<name>/

| 文件 | 要点 |
|---|---|
| `<core>.py` | dataclass + to_dict;入参校验 raise ValueError;**生成类必须内置 round-trip guard**（产出先过对应解析器:parse_contract / parse_rules_text / lint_text / ast.parse） |
| `i18n.py` | `make_lookup` 的 zh/en 字典,键名 rpt_*/col_*/编码键 |
| `report.py` | `md_table` + `normalize_lang`;分级标记用 common.severity 的 SEVERITY_MARK/DRIFT_MARK |
| `advisor_llm.py` | `one_shot(agent, _SYSTEM_ZH, _SYSTEM_EN, payload, lang)`,严格可选;敏感数据只发元数据 |
| `api.py` | `make_text_router(...)`,request_model 字段齐 lang/report/llm |
| `tools.py` | 字符串进 markdown 出,双语 docstring,空输入/ValueError 友好返回 |
| `manifest.py` | AgentManifest + ToolManifest;**keywords 不得抢邻居署名问法**（见第 5 步） |
| `__init__.py` | 中文一行题注 + Deterministic core 段;sorted __all__ |

复用优先:行数据 `sample_profile.parse_rows`;DDL
`schema_drift.parse_schema_script`;血缘 `quality_trace.build_graph_from_sql`;
语句形状 `sql_diff.statement_shapes`;敏感判定 `mask_preview.detect_category`。

## 2. CLI（cli_cmds/quality_ops.py）

`@click.command` + `report_options`;共用件:`_read/_emit/fail_check/
fail_on_high/append_llm_note/require_with`;台账三件套
`--history`(track_history,**数值-only**,worse_key 必填)+`--trend N`+
`--fail-on-trend`(rising_trend)。register() 里 add_command;命令名全仓唯一
（tests/test_collision_guards.py 兜底）。

## 3. 示例与测试

examples/<slug>_demo/ 的演示输入要把每个分级编码都打中一次。
后端测试覆盖:核心语义、分级边界、bad inputs、report 双语、CLI
markdown/json/gate 双向、tool、API 200/400。页面测试只填 spec 的 TODO。

## 4. 前端收尾

编辑 frontend/<name>/src/{App,api,i18n};然后
`cd frontend && npm install && npx prettier --write <name>/src &&
(cd <name> && npm run lint && npm run build)`。

## 5. 守卫

领域与既有工具相邻时,在 tests/test_collision_guards.py 的 PINS 补一条
**对方**的署名问法。提交前 `python scripts/check_workflow.py` 全 PASS:
报告(docs/reports/)需原样粘贴本次 gate 的 [PASS] 行。
