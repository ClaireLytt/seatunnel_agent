# 02: React 页 A — 骨架 + 分析/上传/下载/双桥接/历史

**What to build:** 用户在 React `/dataskew` 完成核心闭环：粘贴或上传 SQL、
选方言与模式、开始分析（llm 失败回退 banner）、看报告与优化 SQL 代码块、
前端 Blob 下载报告 .md 与优化 .sql、清空重置；sql_review 送来的 SQL 自动
预填（localStorage 桥）；分析历史可刷新/载入。zh/en 与暗色正确。

**Blocked by:** 01 (API 层)

**Status:** ready-for-agent

- [ ] before 截图（zh/en × 亮/暗）存 .scratch/dataskew-react/screenshots/（退役前）
- [ ] workspace frontend/data_skew（uitest 骨架 + sql_transpile 参照），
      双栏布局、i18n 字典原样搬
- [ ] 分析闭环：dialect/mode 控件 + /analyze + 报告渲染 + 优化 SQL SqlView
- [ ] SQL 文件上传（纯前端读文件，截断 200k）、清空、Blob 下载 ×2
- [ ] localStorage `st_dataskew_sql` pickup（排干）
- [ ] 历史区：刷新（下拉 + markdown 表）、载入回填 SQL/方言
- [ ] ruff / mypy / workspace lint+build 通过（尚不 cutover）
