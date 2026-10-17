# 批次结果报告:text2sql 票 #66 图表与导出 + #65 评审修正(2026-10-17)

## 批准依据

> 用户 /implement 驱动 frontier;#65 双轴评审发现随本批修复。

## 已完成(TDD)

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高(#65 评审硬 bug) | 真 agent 的 execute_sql 结果是 JSON 字符串,SSE 映射曾按 dict 取值必崩 —— 加解析;RealShapeAgent 测试先红后绿 | api.py, tests/test_t2s_chat_api.py | 本批次 commit |
| 高(#65 评审) | text_delta 事件透传为 delta,前端合并进当前气泡(真·逐 token 流式);同会话并发 /chat 返回 409(原会挂死) | api.py, ChatPanel.tsx, tests | 本批次 commit |
| 高(#66) | result 事件携带服务端 detect_chart_type;前端 ResultBlock:Recharts(bar/line/pie/scatter)+手动类型覆盖+None、>20 行分页(50/页)、CSV 客户端导出、图表 PNG 导出(SVG→canvas) | api.py, frontend/text2sql/src/ResultBlock.tsx 等 | 本批次 commit |
| 中 | 浏览器冒烟扩展:60 行分页 1/2→翻页 r59、auto-detect 超上限返回 None 时手动选 bar 出图、CSV 控件可见 | tests/test_t2s_page.py | 本批次 commit |

## 验证结果

```
RED: chart_type 测试 1 failed;字符串结果/delta/409 三测 3 failed
GREEN: tests/test_t2s_chat_api.py 9 passed ×5 连跑(修掉两处测试竞态:探测 POST 污染会话、stop 抢先首事件的合法时序)
冒烟: tests/test_t2s_page.py 2 passed(Recharts ResponsiveContainer 需直接包 chart 组件 —— 自定义中间组件吞掉尺寸 props,已修)
全量: pytest -q -> 2928 passed, 1 skipped(+5);mypy Success;ruff All checks passed!
前端: npm build / lint 全过
```

## 前后差异

- 前:真 LLM 查询会因字符串结果崩断 SSE;长回答整段一次性出现;结果只有静态表。
- 后:真查询全链路可用,逐 token 流式;结果表分页;Recharts 交互图(含手动类型)、CSV/PNG 导出。
- 测试:2923 → 2928 passed。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 富分析卡 HTML 透传仍缺(#65 评审确认为对票面文本的缺口,已显式顺延) | /chat 映射 | 混合协议后续票 | 对应卡片功能缺席 | #68-#71;用户如不认可顺延请指出 |
| 低 | stop 后 worker 线程仍跑完整轮(浪费一轮 LLM) | api.py work() | 终止事件只断流 | token 浪费 | 评审判断项,暂接受 |
| 低 | 饼图切片颜色含语义色复用 | ResultBlock PIE_COLORS | 中性+语义混排 | 观感 | 视反馈调整 |

## 未执行的步骤

- uitest smoke 全套件:未执行 —— 不触及既有 91 条路径;CI 兜底。
