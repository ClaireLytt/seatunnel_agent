# 03: text2sql 控件补全

**What to build:** Text2SQL · Chat BI 页每个按钮至少被一条确定性测试触发:聊天区 Enter 发送、Stop、上一页、CSV 下载、PNG 导出、👍/👎 反馈;Schema 面板 select-all 与 reload;History 的 refresh/qlog CSV 下载/delete-selected/resume-session;Favorites 的 rename(含 Enter 提交)/delete/refresh;Metrics 的行展开与 use metric;Boards 的 render/delete/refresh(含 Enter 建板);Subscriptions 的真正 create/启停/run-now/delete/refresh;模板 chip 预填问题。

**Blocked by:** 01(下载断言模式)

**Status:** ready-for-agent

- [ ] 聊天:Enter 键发送出结果;Stop 可中断;上一页翻页;CSV 与 PNG `expect_download` 真测;👍/👎 点击后状态可见
- [ ] Schema 面板:select-all 全选、reload 重载后表清单仍在
- [ ] History:refresh / qlog.csv 下载 / delete-selected / resume-session 各验一次
- [ ] Favorites:rename(Enter 与按钮两路)、delete、refresh;Metrics:行展开 + use metric 预填
- [ ] Boards:Enter 建板、render、delete、refresh;Subscriptions:create→启停→run-now→delete 闭环
- [ ] 模板 chip 点击后问题输入框被预填
- [ ] `pytest -m uitest -k t2s` 通过;ruff/mypy 通过
