# 批次结果报告:票 #100 Text2SQL SessionManager(2026-10-17)

## 批准依据

> 架构评审Ⅱ候选②;spec #99;用户 /implement 驱动。

## 已完成(TDD)

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 新模块 sessions.py:SessionManager(LRU 存储、单一 SessionEntry 形态、活跃流注册表与全部锁、create/get/replace/put_legacy/attach_stream/finish_stream/stop) | agents/data/text2sql/sessions.py | 本批次 commit |
| 高 | 单测 5 条(LRU 驱逐、触达刷新、闲置 stop=False、并发流拒绝与释放、legacy 同形态)先红后绿 | tests/test_t2s_sessions.py | 本批次 commit |
| 高 | api.py 瘦身:全局三件套删除、isinstance 分支清零、docstring 修正为 12 端点真名单 | agents/data/text2sql/api.py | 本批次 commit |
| 中 | agent 公开缝 set_event_hook(传输层不再写私有属性);hook 挂接移入 try 内(失败也能终止流) | agents/data/text2sql/agent.py, api.py | 本批次 commit |

chart 检测已在 #66 评审时置于 result 映射分支,本票核对无传输层内联残留。

## 验证结果

```
RED:  tests/test_t2s_sessions.py -> module missing(1 error)
GREEN: sessions 5 + chat 9 + connect 5 = 19 passed
      —— 14 条协议测试【断言零改动】;fake agent 各增 3 行以实现新的公开缝
      set_event_hook(fake 即缝契约的消费者,属契约演进而非行为变化,如实记录)
全量: pytest -q -> 2935 passed, 1 skipped(+5);mypy Success;ruff All checks passed!
页面冒烟: 2 passed(HTTP 行为对等)
踩坑×2(均当场修复): ① Edit 插入吞掉 __init__ 尾部语句(ast 过但运行时必坏,靠回看上下文抓出);
  ② 测试 fake 未实现新缝导致 work 线程在 try 外崩、SSE 挂死 —— 已把 hook 挂接移入 try 兜底
```

## 评审修正(双轴)

- replace_agent 原子化(锁内取-换,会话消失返回 None -> 端点 404;assert 移除)并补单测先红后绿
- chart 检测移入 chart.result_snapshot(格式化层),SSE 循环只剩一行调用 -- 补齐 spec #99 该决策
- 测试 fake 的 3 处重复 set_event_hook 覆盖删除
- check_workflow 输出(§7.8,amend 前快照;amend 后终态见对话):

```
[PASS] AI 署名: 无 AI 署名(范围 origin/agent-ui..HEAD)
[FAIL] 工作区: 工作区不干净:
?? cw_out.txt
[FAIL] 报告落盘: 未推送 commit 改了 src/tests 但 docs/reports/ 无新报告(范围 origin/agent-ui..HEAD)
```

## 前后差异

- 前:api.py 653 行,3 个模块级可变全局,两种会话形态 4 处 isinstance,私有属性跨模块直写。
- 后:会话域一个 deep module;api.py 端点薄接线;#68-#71 直接继承 SessionManager 接口。
- 测试:2930 → 2935 passed。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | chat_history.py 的第三个手搓缓存未并入 | chat_history.py:47-50 | spec 明确 Out of Scope | 包内仍两套缓存 | #69(history 票)顺路评估 |
| 低 | 挂死类故障暴露 SSE 无服务端超时 | 本票踩坑② | 流无 max 时长 | 极端下连接悬挂 | 候选③ common/sse.py 时加 heartbeat/timeout |

## 未执行的步骤

- smoke 全套件:未执行 —— HTTP 行为对等由 19 条协议测试+页面冒烟证明;PR CI 兜底。
