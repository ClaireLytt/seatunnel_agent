# 批次结果报告:agent-loop-deepen(六个 ReAct 循环收敛为一个深模块)(2026-10-23)

## 批准依据

> 用户通过 `/implement-spec` 批准实现 `.scratch/agent-loop-deepen/spec.md`;票 01 完成后检查点,用户回复 "go on";中途确认 "继续"。

## 已完成

| 票 | 内容 | commit |
| --- | --- | --- |
| 01 | ToolLoopAgent 新增 4+2 个可选 seam:on_event(turn/tool_call/step/text_delta/usage)、stop_event(轮间+工具间,自动补 cancelled tool_result)、system_hint、truncate、on_limit(替代强制总结轮);LoopResult.stopped;10 例离线 loop 测试(tests/test_agent_core_loop.py) | 22177f3(seam 扩展续在 ad23843) |
| 02 | orchestrator 迁移:删除漂移的原始循环与重复 Step/Result(OrchestratorResult = LoopResult);本地化步限兜底保留在 agent 侧 | 3db6daa |
| 03 | sql_review 迁移:事件适配器保留 thinking/text/tool_call/tool_result/final_answer 协议与 Rich CLI 显示;on_limit 落回 last_report | ad23843 |
| 04 | data_lineage 迁移:同 03 模式 | a96b693 |
| 05 | text2sql 迁移:sql_retry/cache_hit 事件在适配器中由 step 事件派生 | 0b6f006 |
| 06 | seatunnel 迁移:stop/text_delta/usage 走共享 seam,context hint 走 system_hint,truncate_messages 走截断策略;重试上限语义保留(工具包装器触发 stop 后 agent 侧补总结轮) | 3713cee |

循环实现:6 份 → **1 份**(各 agent 的 `_agent_loop` 仅剩适配器+ToolSpec 组装,无循环体;`grep "for .* in range(MAX_LOOP_ITERATIONS)"` 仅 agent_core 命中)。注入式 ScriptedClient 测试 seam 现对全部 9 个 adopter 可用,每个迁移 agent 新增 1 例离线 loop 测试。

## 行为契约变化(有意,已记录)

1. 旧的按迭代 "step"(iteration/phase)事件不再发出 —— 全仓无消费者;seatunnel 的 1 例断言此事件的测试改为断言新协议。
2. 停止时 dangling tool_use 的占位文案由 `{"error": "Cancelled: stopped by user"}` 统一为共享循环的 `cancelled: stopped by user`(仅喂给模型,不面向用户);相应断言改为大小写不敏感。
3. seatunnel 重试上限在"同一批多个工具调用"边缘情形下,其余工具调用会收到 cancelled 占位(旧实现会执行完整批);单工具批(实际情形)语义不变。

## 验证结果

```
ruff check src tests            -> All checks passed!
mypy                            -> Success: no issues found in 106 source files
票级定向测试:
  loop 新测试                   -> 10 passed
  orchestrator                  -> 44 passed
  sql_review                    -> 313 passed
  data_lineage(+impact)        -> 138 passed + 187 passed(含 impact)
  text2sql(3 套)              -> 404 passed;新 loop 测试 1 passed
  seatunnel(agent/api/bot)    -> 86 passed;page 5 passed
pytest -q(全量)               -> 3347 passed, 1 skipped, 242 deselected
python -m …ui_testing run --suite smoke --no-llm -> PASS 16 · FAIL 0(runs/20261023_200506/report.html)
pytest tests/test_t2s_page.py   -> 4 failed, 14 passed(4 例为批前已知 API_KEY 环境问题,与本批无关)
python scripts/check_workflow.py -> 报告提交后复跑,见对话
```

## 前后差异

- 全量 pytest:3332(批前)→ **3347 passed**(+15:10 例 loop 测试 + 每迁移 agent 1 例 + orchestrator 委派断言)。
- 代码:12 文件 +697/−468(循环体删除 5 份;新增为共享 seam、事件适配器与测试 —— 本批目标是局部性/可测性,非行数)。
- uitest smoke 16/16 PASS,与批前一致。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | test_t2s_page.py 4 例失败(批前已有) | 本批前 stash 验证同样失败;服务端 `RuntimeError: API_KEY is not set` | 本机 .env 缺 API_KEY | 本机 t2s 页面测试不全绿 | 配置 .env 后复跑 |
| 低 | 各 agent 的事件适配器形状相似(thinking/text/tool_call/tool_result 映射 ×4) | sql_review/data_lineage/text2sql/seatunnel agent.py | 本批刻意保守:先收敛循环,不动协议 | ~30 行/份的相似代码 | 若后续做候选 5(SSE 收敛),可把适配器并入共享事件→SSE 桥 |

## 未执行的步骤

- 真浏览器手工验证 seatunnel Stop 按钮:未执行(由 test_agent.py 停止语义测试 + seatunnel page 测试 + uitest smoke 覆盖;如需人工复核请在 /seatunnel 页点击验证)。
- /implement-spec 模板的 worktree/并行/集成分支/PR/code-review 子代理流程:未执行(CLAUDE.md 禁止,串行于 dev)。
