# 批次结果报告:方言扩展 Phase 2 调度引擎(2026-10-31)

## 批准依据

> 用户技术栈清单含调度三件套(Airflow、DolphinScheduler、Azkaban)并指示"指定这些数据库的扩展 不要局限于hive";"go on" 进入 Phase 2。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | generate_dag 增加 engine 参数:airflow(dag.py,ast.parse 回检)/ dolphinscheduler(taskDefinitionList+taskRelationList JSON,json.loads 回检,root 关系 preTaskCode=0)/ azkaban(Flow 2.0 YAML,yaml.safe_load 回检) | src/seatunnel_agent/agents/data/dag_gen/generator.py | (本批) |
| 中 | 报告按 engine 切换标题与代码块语言(python/json/yaml),i18n 新增 4 组键 | dag_gen/report.py, dag_gen/i18n.py | (本批) |
| 中 | CLI --engine 选项、--py-out 文案通用化;API 请求模型加 engine 字段 | cli_cmds/qo_build.py, dag_gen/api.py | (本批) |
| 中 | 新增 engine 测试(DS/azkaban 回结构断言、报告、CLI .flow 落盘、API、无效 engine) | tests/test_dag_gen.py | (本批) |

## 验证结果

```
python -m pytest tests/test_dag_gen.py tests/test_sql_diff.py -q -> 27 passed in 2.90s
python -m pytest tests/test_collision_guards.py -q -> 2 passed
ruff check src tests -> All checks passed!
```

```
(gate 输出占位,提交后回填)
```

## 前后差异

- dag_gen:1 引擎(Airflow)→ 3 引擎;测试 11 → 13 条(含报告/CLI/API 断言增补)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | DS 定义 JSON 为可导入骨架,code 用 1..N 顺序号,导入前需按实例分配真实 code | generator._render_dolphinscheduler | DS code 由服务端发号 | 导入时手工替换或走 openapi | 文件头 description 已注明草稿性质 |

## 未执行的步骤

Phase 3(其余 agent --dialect 透传/文案审计)待下一批。
