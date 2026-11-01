# 批次结果报告:架构加深·data_skew 门面(2026-10-31)

## 批准依据

> 用户:"上上次的improve-codebase-architecture生成的html完成进度接着继续"——继续
> 架构评审(architecture-review-20261030.html)的落地,候选 1/2 已完成,本批次落地
> 候选 4(data_skew 对外门面)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | data_skew 门面:外部实际用到的 54 个名字全部提升进 `__init__.py` 并排序导出 | src/seatunnel_agent/agents/data/data_skew/__init__.py | 本批 |
| 高 | runtime 事实接口去私名:`_iter_eventlog_lines`→`iter_eventlog_lines`、`_fmt_bytes`→`fmt_eventlog_bytes`、`_stage_name`→`stage_name`(shuffle_dist 同步改用公名) | src/seatunnel_agent/agents/data/data_skew/{runtime,shuffle_dist}.py | 本批 |
| 高 | 三个外部调用方改走门面,不再直捣 8+ 个子模块 | src/seatunnel_agent/agents/data/mcp_toolbox/core.py · src/seatunnel_agent/agents/data/text2sql/tools_sql.py · src/seatunnel_agent/cli_cmds/skew.py | 本批 |
| 中 | CLI 路径测试 patch 目标同步收口到门面(包内 api.py 路径的测试保持 patch 子模块) | tests/test_data_skew.py | 本批 |
| 中 | 去除 make_text_router 的 3 处 type: ignore:请求模型注解改为注册前绑定 `run.__annotations__` | src/seatunnel_agent/common/api_factory.py | 本批 |

## 验证结果

```
python -m ruff check src tests                       -> All checks passed!
python -m pytest tests/test_data_skew.py tests/test_shuffle_dist.py tests/test_mcp_toolbox.py -q
                                                     -> 254 passed, 2 warnings
python -m pytest tests -q -k "api or router or factory"
                                                     -> 465 passed, 3688 deselected
python -m pytest tests -q                            -> 3854 passed, 1 skipped, 298 deselected(test_web_task 并发偶发 error,单跑 18 passed)
python -m mypy src                                   -> Found 206 errors(与改动前基线逐字节一致,无新增)
python scripts/check_workflow.py ->
[PASS] AI 署名: 无禁止署名字样(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告已粘贴验证输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```

## 前后差异

- 测试类:改动前 5 failed, 564 passed(CLI webhook/flink 测试 patch 子模块、门面绑定早于 patch);
  改动后相关套件 254 passed、全量 3854 passed,0 失败。
- 跨包契约:改动前外部模块 import data_skew 的 8+ 个子模块(含 3 个下划线私名);
  改动后 cli_cmds/skew.py、mcp_toolbox、text2sql 全部只 import `agents.data.data_skew`
  门面(grep `agents\.data\.data_skew\.[a-z]` 在 src/ 下除包内与 docstring 外为 0)。
- floor:改动前 origin/fresh..HEAD 新增 3 处 type: ignore;改动后 0。

## 遗留

- 评审候选 3(LLM 三元组)已随候选 1 落地;候选 5/6 评审已否决,不做。
- tests/ 中对 data_skew 子模块的直接 import 保留:monkeypatch 包内实现路径需要真实子模块。
