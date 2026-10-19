# 05: 方言切换横切 + 长尾控件

**What to build:** 把"方言下拉只看不切"的横切缺口补齐:change_impact、metric_diff、pii_scan、schema_drift、sql_fmt、sql_testgen、sql_review、data_lineage、data_skew 各增一条"切换到非默认方言后主流程仍出正确结果"的用例;sql_transpile 源方言切换为具体方言(非 auto)。长尾:sql_review 的 → Transpile 跨页按钮(expect_popup + localStorage 桥)与 Stats Refresh;sql_testgen 的行数滑条非默认值生效。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] 上述每页至少一条非默认方言用例,断言结果区正常渲染(无 traceback/错误态)
- [ ] sql_transpile:源方言显式选定(非 auto)后翻译成功
- [ ] sql_review:→ Transpile 弹开 /transpile 且 SQL 经 localStorage 桥带过去;Stats Refresh 点击后统计区更新
- [ ] sql_testgen:滑条改为非默认行数,生成行数随之变化
- [ ] `pytest -m uitest` 相关页通过;ruff/mypy 通过
