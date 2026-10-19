# 01: 下载与剪贴板真测横切(模式 + 既有按钮落地)

**What to build:** 用户点击任何"下载/复制"类按钮时,测试能证明真的拿到了文件/剪贴板内容。建立两个可复用断言模式(`page.expect_download()` 校验文件名+内容非空;browser context clipboard 权限 + `navigator.clipboard.readText()`),并用它们把当前只断言"可见"的控件补成真测:data_skew 的下载报告/下载优化 SQL、sql_review 的 Download Report (.md)、config_migrate 的复制配置、data_skew 与 sql_transpile 的 Copy SQL。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] data_skew:分析后点击两个下载按钮,`expect_download` 断言文件名(data_skew_report.md / my_task_optimized.sql)且内容非空
- [ ] sql_review:审查后点击 Download Report,断言 sql_review_report.md 下载成功且非空
- [ ] config_migrate:迁移后点击复制按钮,剪贴板内容等于生成的配置
- [ ] data_skew / sql_transpile:Copy SQL 按钮点击后剪贴板包含对应 SQL
- [ ] 复用模式可被后续票直接套用(写法与既有 page tests 风格一致)
- [ ] `pytest -m uitest -k "dataskew or sql_review or config_migrate or transpile"` 通过;ruff/mypy 通过
