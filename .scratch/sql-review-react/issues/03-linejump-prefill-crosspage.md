# 03: 行跳转 + URL 预填 + 跨页传 SQL

**What to build:** 用户点击报告中的行号引用，左侧 SQL 对应行被选中/高亮；带 `?sql=&dialect=` 打开页面时表单预填；"转到 Transpile / Data Skew"按钮把当前 SQL 带到目标页（localStorage + 新开页机制保留）。

**Blocked by:** 01

**Status:** ready-for-agent

- [ ] 报告行号点击 → SQL 行高亮/选中
- [ ] ?sql=&dialect= 预填生效
- [ ] 转 Transpile / DataSkew 携带 SQL
