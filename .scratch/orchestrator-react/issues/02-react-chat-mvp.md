# 02: React 聊天页最小闭环 + manifest 切换

**What to build:** 用户打开 /orchestrator 看到 React 页(engineering-paper 主题,禁蓝紫渐变):输入消息、发送后流式看到步骤与最终回答,New session 重开会话。manifest 切 external 模式,workspace 目录名 = manifest.name,`ui --build` 可构建并打开真页面。参照 frontend/uitest 工程结构与 text2sql 聊天形态,复用 @shared(sse/card/theme/lang)。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] frontend/orchestrator workspace 建立并加入 workspaces 列表
- [ ] 聊天收发 + 流式步骤 + New session 可用
- [ ] manifest external=True, render="" 切换完成,路由 /orchestrator 不变
- [ ] npm lint + build 通过;`seatunnel-agent ui --build` 页面可打开
