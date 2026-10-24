# 05: uitest 报告 iframe 放行脚本

**What to build:** 在 UI Testing Agent 页点 "View" 查看历史报告时,浏览器 console 零错误:报告 iframe 的 sandbox 允许脚本运行,报告内的交互部分可用。按报告 HTML 实际需要决定 sandbox 取值——优先只给 `allow-scripts`,避免 `allow-scripts` + `allow-same-origin` 同源组合带来的沙箱逃逸;仅当报告确实依赖同源能力时才保留两者并说明理由。uitest YAML 套件新增一条用例:打开报告并断言无 console error(沿用现有用例格式)。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 真浏览器:点 View 打开报告,DevTools console 无 "Blocked script execution" 等 error;截图留证
- [ ] uitest 新用例(打开报告 → console 无错误)纳入套件并通过;注意用例计数与 YAML 对账断言同步更新
- [ ] `npm run lint --workspace uitest` + `npm run build --workspace uitest` 通过(在 frontend/ 下执行)
- [ ] `python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm` → PASS,附报告路径
