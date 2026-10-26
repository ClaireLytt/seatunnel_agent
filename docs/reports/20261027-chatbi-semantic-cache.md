# 批次结果报告:chatbi 语义缓存(2026-10-27)

## 批准依据

> 用户对第四轮候选清单(建议"1(语义缓存)单独一批")回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `normalize_question` + `ExampleStore.exact_match`:大小写/空白/末尾标点归一后的完全同问匹配(保守设计:改写永不命中,因为改写可能改变日期/过滤) | examples.py | 本批 |
| 高 | `Text2SQLAgent.run` 前置缓存:命中已验证示例 → 复用 SQL 走完整 execute_sql 链路(validator/白名单/LIMIT/脱敏/qlog),**零 LLM 调用**;执行失败(schema 漂移等)静默回落 LLM;仅单轮入口,多轮追问不缓存;`T2S_SEMANTIC_CACHE=0` 关闭 | agent.py | 本批 |
| — | 指南"语义缓存"小节 | docs/chat_bi_guide.md | 本批 |

闭环已有:👍 自动入库(问题, 最终 SQL)→ 下次同问零成本;👎 移除示例 → 重新走生成。

新增测试 4 条:归一化与 exact_match / 命中跳过 LLM(FakeLLM 计数为 0,结果卡可用)/ 坏 SQL 回落 LLM / 环境变量关闭。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 107 source files
python -m pytest tests/test_text2sql_examples.py -q -> 16 passed in 4.77s
python -m pytest -q          -> 3442 passed, 1 skipped, 243 deselected in 150.87s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3438 → 3442 passed(+4)。
- 行为:与已验证示例完全同问的单轮提问从"全量 LLM 生成"变为"0 token 直出"(答案明确标注缓存命中与退出方式);其余路径不变。
- 非 UI 改动,uitest 未执行。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 缓存命中未在 qlog extra 里单独打 cache_hit 标记(走 execute_sql 的常规日志) | agent.py _semantic_cache_answer | execute_sql 工具内部统一记日志,外部补标记需改工具签名 | 治理侧统计不出缓存命中率 | 需要时给 execute_sql 输入加 qlog_extra 透传 |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动;缓存只在单轮 run 入口,UI chat 走多轮不受影响)。
- 其余无。
