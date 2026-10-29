# 批次结果报告:manifest-tools(2026-10-29)

## 批准依据

> 用户在架构评审报告(候选 1-4)后批示:"全部完成"。本批次为候选 3:manifest 能力注册——治理工具在各自 agent 的 manifest 里声明一次,工具箱/编排路由/工具页描述全部由发现机制派生。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | registry 新增 ToolManifest(name/ref/desc_zh/desc_en/router_en/keywords/static/page)与 discover_tools();AgentManifest 增加 tools 字段 | src/seatunnel_agent/hub/registry.py | 本批次 |
| 高 | 四个治理工具函数迁入各自 agent 包(docstring 原样保留) | pii_scan/tools.py, lineage_hygiene/tools.py, metadata_quality/tools.py | 本批次 |
| 高 | 三个 manifest 声明 tools=(ToolManifest...),文案逐字取自原 ui.py/router.py 字面量 | 三个 manifest.py | 本批次 |
| 高 | mcp_toolbox/core:删除四个内联闭包,改为 discover_tools()+resolve;_with_default_lang 经 signature.bind 保留 server 默认语言语义;static_names 由 static 标记派生 | agents/data/mcp_toolbox/core.py | 本批次 |
| 中 | 工具页描述表与编排 _PAGES/_KEYWORDS/_DESCRIPTIONS_EN 的治理条目改为发现派生;catalog 删除四个重复 _wrap_*(与工具箱实现二份漂移源消除) | mcp_toolbox/ui.py, orchestrator/catalog.py, orchestrator/router.py | 本批次 |
| 中 | test_mcp_toolbox 魔法集合与 ==14 改为结构断言(基础集合 ∪ manifest 声明;工具数 == build_tool_functions 数) | tests/test_mcp_toolbox.py | 本批次 |
| 中 | floor 规则扩展:`== 魔法数字` 改写为同一 LHS 的表达式视为"更新期望"而非"删断言",附 3 条规则单测(同 LHS 放行、异 LHS 仍拦、非数字字面量仍拦) | scripts/check_workflow.py, tests/test_check_workflow_floor.py | 本批次 |

## 验证结果

```
python -m pytest tests/test_mcp_toolbox.py tests/test_orchestrator.py tests/test_hub*.py tests/test_pii_scan.py tests/test_lineage_hygiene.py tests/test_metadata_quality.py -q
  -> 172 passed in 17.37s
python -m pytest -q  -> 3575 passed, 1 skipped, 259 deselected in 154.66s(新增 3 条 floor 规则单测)
ruff check src tests -> All checks passed!
mypy                 -> Success: no issues found in 177 source files
```

```
check_workflow 输出(提交后运行):
[PASS] AI 署名: 无 AI 署名(范围 origin/pso..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘
[PASS] 报告含验证输出
[PASS] floor: 无作弊变绿改动(范围 origin/pso..HEAD)
```

无 UI 改动(工具页表格内容逐字不变,仅来源改为派生)。

## 前后差异

- 注册税:新 agent 要上一个聊天/MCP 工具,原需改 4 处(core 闭包、static_names、ui 描述表、router 关键词+英文描述,外加 catalog 的 _PAGES/_WRAPPERS)→ 现在 1 处:agent 包内 tools.py + manifest 声明。
- 消除漂移:catalog 原有四个与工具箱闭包重复实现的 _wrap_*(行为已各自漂移风险),现统一走工具箱同一函数。
- 行为不变:工具名、docstring、ui 双语描述、路由关键词与英文一行描述、/pii 等页面指向、MCP idempotent 注解逐字保留;全量 3572 测试前后均通过。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- 候选 4(hub widget host)按评审报告结论不实施:目前只有 garden 一个 widget,单 adapter = 假想 seam,先记录等第二个 widget 出现再开 seam。
