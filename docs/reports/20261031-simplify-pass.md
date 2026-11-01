# 批次结果报告:simplify 质量自审落地(2026-10-31)

## 批准依据

> "go on"（/simplify 四视角并行审查 4642 行新增代码后的修复落地）

## 已完成（按审查视角去重后）

| 来源 | 修复 | 文件 |
| --- | --- | --- |
| 效率 | diff_dags 透传已算好的 optimize 结果，三处调用点不再重复整套分析 | dag_optimize/{optimizer,api,tools}.py, cli |
| 效率 | 冗余边检测改为逆拓扑序后代集合预计算，witness BFS 只跑已判定冗余的边 | dag_optimize/optimizer.py |
| 效率 | _critical_path 终点选取去掉全量排序；edges 属性在 optimize 内绑定一次 | dag_optimize/optimizer.py |
| 效率 | rerun 下游闭包改为一次 BFS + 拓扑序传播，去掉重推不动点与无效 sorted | rerun_plan/planner.py |
| 复用/层次 | _read_whitelisted 六份拷贝收口为 api_guard.read_whitelisted_file | common/api_guard.py + 6 个 api.py |
| 化简 | api 层 except (ValueError,TypeError)+except Exception 双联死代码收敛(5处) | 4 个 api.py |
| 复用/化简 | _emit/_track_history 迁入 check_runner(emit_payload/track_history 公名)，checks.py 两命令与两处 gate 改用 fail_check——顺带修掉 json 模式下 gate 红字污染 stdout 的真实回归 | check_runner.py, pipeline_ops.py, checks.py |
| 化简 | backfill_sql 规格 markdown 收敛为 report.render_specs_markdown(tool/API/CLI 三处共用)；pipemigrate 的 collect_scripts/render_advice 入包，api 与 CLI 不再各写一份 | backfill_sql/{report,tools,api}.py, pipeline_migrate/{advisor_llm,api}.py, cli |
| 化简 | dag_optimize._makespan 公名化为 makespan(rerun 跨包引用不再依赖下划线私名) | optimizer.py, rerun_plan/planner.py |

## 记录的跳过（非争辩，注明理由）

- 效率#3 瓶颈敏感度的两遍 DP 重写：收益仅在数千节点深链场景,重写复杂度高,保留现实现（已修其中的全量排序热点）。
- witness BFS 内部 sorted:是 witness path 确定性的来源,测试依赖,保留。
- 前端三项（共享样式常量替换、handoff 收敛进 shared、LlmCheckbox 共享组件）:纯机械、零行为变化但涉及 5-7 个 app 数十处 JSX,PR 已在 review 阶段,churn 代价大于重复代价——记为合入后 follow-up。
- useRunner/RunPage 大改:同上,且审查者自己也标注"有 God component 风险"。

## 验证结果

```
pytest 8 个 agent/CLI 测试文件 -> 107 passed
ruff check src/seatunnel_agent tests -> All checks passed!
python -m mypy 新增五包 + cli + api_guard -> Success(45 files)
python scripts/check_workflow.py --range origin/main...HEAD ->
  [PASS] x6（全绿）
```

## 前后差异

- 净删除约 180 行重复代码;安全敏感的白名单读取从 6 份收敛为 1 份;
  两个 CI gate 在 --format json 下不再污染 stdout。
