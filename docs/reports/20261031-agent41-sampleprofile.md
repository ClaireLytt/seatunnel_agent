# 批次结果报告:Agent 41 数据抽样剖析 sample_profile(2026-10-31)

## 批准依据

> 用户:"适配以上的agent 制定好方案后一步步执行"(36–47 清单)。方案文档
> docs/data_agents_36_47_plan.md 已随上一提交落盘,本批为里程碑 1:
> 41 sample_profile(profiler 是 36/40 的地基)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性核心:CSV/JSONL 解析、等距抽样、逐列剖面(类型/空值/唯一/范围/高频/格式桶)、SP001–SP006 异常规则(带行号定位) | src/seatunnel_agent/agents/data/sample_profile/profiler.py | 本批 |
| 高 | zh/en 报告 + i18n + LLM 体检通报(opt-in) | sample_profile/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest(hub 卡片自动发现) | sample_profile/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent sampleprofile`(--max-rows/--llm/--fail-on-high gate),新 cli_cmds/quality_ops.py 注册 | src/seatunnel_agent/cli_cmds/{quality_ops,__init__}.py | 本批 |
| 高 | React 页(useRunner,等距抽样上限输入,demo 预填) | frontend/sample_profile/* + workspace 注册 | 本批 |
| 中 | 示例数据 + 单测 24 条 + 页面回归 2 条 | examples/sampleprofile_demo/orders.csv · tests/test_sample_profile.py · tests/test_sampleprofile_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_sample_profile.py -q    -> 24 passed
python -m pytest -m uitest tests/test_sampleprofile_page.py -q -> 2 passed
python -m pytest tests/test_sample_profile.py tests/test_cli.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 81 passed
seatunnel-agent sampleprofile -f examples/sampleprofile_demo/orders.csv -> 列剖面 + 5 条发现(SP001/SP003/SP004×2/SP006)
npm run build (frontend/sample_profile)             -> built in 4.08s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:改动前 data workspace 无抽样剖析能力;改动后 hub 多一张
  quality 组卡片(/sampleprofile),REST/MCP/CLI/React 四入口齐备。
- 测试:新增 24 条单测 + 2 条页面回归,全部通过;相关套件 81 passed 无回归。

## 遗留

- 里程碑 2–12(36/37/39/38/40 与 42–47)按 docs/data_agents_36_47_plan.md
  逐个落地,每个独立提交。
