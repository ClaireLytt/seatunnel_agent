# 批次结果报告:Agent 53 任务失败归因 task_failure(2026-10-31)

## 批准依据

> 用户:"think about new functions"后"按你的排序执行"(排序中 B 组之后
> 为 53 task_failure:失败日志归类/同根因聚类/重试有效性,与 sla_trace
> 的延迟归因互补)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 确定性归因核心:失败导出(CSV/JSON)→ 六类错误归类(依赖缺失/资源/超时/连接/数据异常/代码错误)+ 归一化错误签名聚类(同根因一组,附成员与样例)+ 重试判定(瞬态/无效/部分/未重试) | src/seatunnel_agent/agents/data/task_failure/classifier.py | 本批 |
| 高 | zh/en 报告(聚类表 + 按出现归因的处方清单,指向 backfill/dagconflict/slowquery/datarepair)+ i18n + LLM 失败通报(opt-in) | task_failure/{report,i18n,advisor_llm}.py | 本批 |
| 高 | REST(make_text_router)+ MCP 工具 + manifest(build 组,order 80) | task_failure/{api,tools,manifest,__init__}.py | 本批 |
| 高 | CLI `seatunnel-agent taskfailure`(复用 append_llm_note 帮助函数) | src/seatunnel_agent/cli_cmds/quality_ops.py | 本批 |
| 高 | React 页(useRunner,demo 预填) | frontend/task_failure/* + workspace 注册 | 本批 |
| 中 | 示例导出 + 单测 16 条 + 页面回归 2 条 | examples/taskfailure_demo/failures.json · tests/test_task_failure.py · tests/test_taskfailure_page.py | 本批 |

## 验证结果

```
python -m ruff check src tests                      -> All checks passed!
python -m pytest tests/test_task_failure.py -q      -> 16 passed
python -m pytest -m uitest tests/test_taskfailure_page.py -q -> 2 passed
python -m pytest tests/test_task_failure.py tests/test_hub_pages.py tests/test_mcp_toolbox.py -q -> 64 passed
seatunnel-agent taskfailure -f failures.json -> 7 任务归 5 类,两个分区缺失失败正确聚为一组,重试判定瞬态/无效/未重试各正确
npm run build (frontend/task_failure)               -> built in 2.92s
python scripts/check_workflow.py ->
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 新增 agent:build 组新增 /taskfailure 卡片,REST/MCP/CLI/React 四入口
  齐备;与 sla_trace 分工明确(失败归因 vs 延迟归因)。
- 测试:新增 16 条单测 + 2 条页面回归,全部通过;相关套件 64 passed 无回归。

## 遗留

- 排序继续:54 schedule_advisor → C 套件总览。
