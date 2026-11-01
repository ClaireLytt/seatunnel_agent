# 批次结果报告:性能套件 simplify 四角自查(2026-10-30)

## 批准依据

> "/simplify"（复用/化简/效率/高度四个并行视角审 30-35 + perf_ops 代码后统一修复）

## 已修复(去重后)

| 视角 | 内容 | 文件 |
| --- | --- | --- |
| 高度+化简+效率 | PF003 机制接真:filter_above 真正作为"扫描上方有 Filter"的门槛(逐 scan 置位/复位),删除原无效赋值;ScanInfo 增加内部 filter_above 字段 | sql_perf/analyzer.py |
| 复用 | counts() 改用 common.severity.severity_counts;sql 截断改用 utils.truncate(带 [truncated] 标记) | sql_perf/analyzer.py、advisor_llm.py |
| 复用+化简 | LLM 一次调用胶水抽为 common/llm.one_shot,七个 advisor_llm 全部改走(每个只剩提示词+payload) | common/llm.py + 7 个 advisor_llm.py |
| 复用 | _secs/_size 提升为 common/utils.fmt_secs/fmt_bytes,sql_cost 与 slow_query 两份报告共用 | common/utils.py、sql_cost/report.py、slow_query/report.py |
| 高度 | --lang/--format/--output 三连与 --file/--text 解析上移 check_runner(report_options/read_input),pipeline_ops 与 perf_ops 共用;SEVERITY_RANK 增加 info 档,sqlperf 闸门改走共享 severity_gate | cli_cmds/check_runner.py、pipeline_ops.py、perf_ops.py |
| 高度 | what-if 下沉:estimator.what_if + report.render_what_if(i18n 化,原 CLI 内硬编码中文段删除),CLI 只剩旗标解析 | sql_cost/estimator.py、report.py、i18n.py、perf_ops.py |
| 化简+效率 | estimator 去掉 sides/max_rows 影子累加器(循环后从 card.scans 推导);alias 解析抽 utils.sql_alias_map,index_advisor 与 sql_cost 共用;tools.py 两个同体 except 合一 | sql_cost/estimator.py、index_advisor/advisor.py、sql_cost/tools.py |
| 效率+化简 | diagnoser SQ001 直接保留获胜 StageMetrics,去掉对全部 stage 的二次扫描 | slow_query/diagnoser.py |
| 效率+化简 | 事件扫描改增量(O(n²)→排序+差分);错峰 what-if 改平移 victim 的既有 runs 再扫一遍(不再整场景重排);新增共享 _runs;simulate_peaks_only 并入 | dag_conflict/conflictor.py |
| 效率 | eventlog 行先做子串预筛再 json.loads;sorted 结果复用算 p50/max;setdefault 返回值复用 | data_skew/shuffle_dist.py |
| 化简 | file-or-text 解析抽 api_guard.resolve_file_or_text,sql_perf 与 dag_conflict 两个 router 共用 | common/api_guard.py、两个 api.py |

## 记录跳过(含理由)

- 五份 api.py 的整段 run_and_respond 工厂与十 router 的 make_text_router:新抽象而非复用,评审期 churn 大于重复成本,留作合并后跟进。
- estimator 基线与 what-if 共享一次 sqlglot 解析:输入很小,收益不抵改动面。
- data_skew runtime._fmt_bytes 并入 common:输出格式与 fmt_bytes 有差异,统一会改既有渲染,跳过。
- `except ValueError: raise` 判为死代码一条:实际用于避免二次包装,保留(假阳性)。
- 前端 shared-constants/bridge 重构:此前已记录的合并后跟进项,维持不动。

## 验证结果

```
pytest tests -q (非 uitest) -> 3821 passed, 1 skipped
pytest 性能套件 5 个页面回归 -m uitest -> 8 passed
ruff -> All checks passed; mypy(全部触及文件 44 个) -> 无错误
python scripts/check_workflow.py --range origin/main...HEAD -> [PASS] x6
```

## 前后差异

- 行为唯一变化:PF003 现在按文档语义只在"扫描上方确有 Filter 且下推为空"
  时触发(demo 与既有测试输出不变);其余全部为等价重构,全量测试0差异。
