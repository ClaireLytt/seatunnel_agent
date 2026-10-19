# 02: data_comparison 控件补全

**What to build:** 数据对比页上每个可交互控件至少被一条确定性测试真实触发:count/sample/aggregate 核心动作、profile/batch-full 复合动作、8 个特性手风琴的 run 按钮(incremental/quality/skew/checksum/chunked/partition/customAgg/sql)、GenerationCard 四个按钮与 sync 配置下载、ReportsCard 全套(save/refresh/load/diff)、Templates 的 delete 与批量运行、Trend show、Schedule start/stop、Preset B 侧保存、Export CSV/Excel/独立报告链接。

**Blocked by:** 01(下载断言模式)

**Status:** ready-for-agent

- [ ] 连接 SQLite demo 后,count/sample/aggregate/profile/batch-count/batch-full 各点一次并断言结果卡片出现
- [ ] 8 个特性 run 按钮各点一次,断言各自结果渲染(或确定性提示)
- [ ] GenerationCard:生成同步配置/Diff SQL/血缘/环境对比各点一次;sync 下载链接 `expect_download` 真测
- [ ] ReportsCard save→refresh→load→diff 闭环;Templates delete 与批量运行;Trend show;Schedule start/stop;Preset Save (B)
- [ ] Export CSV / Excel `expect_download` 真测;独立报告链接 expect_popup/新页断言
- [ ] `pytest -m uitest -k datacompare` 通过;ruff/mypy 通过
