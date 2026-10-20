# 03: 功能对齐——Diff 区、历史区、i18n

**What to build:** Diff 折叠区:两个下拉列出 run 结果中无 error 的 cells(profile 名),选两个 → POST /diff → markdown 显示;同一结果不足两个成功 cell 或未选齐时显示 need_two。实验历史折叠区:刷新按钮 → GET /history → 表格(时间/profile 数/preview),无记录显示 no_history。i18n:diff_acc/diff_a/diff_b/diff_btn/hist_acc/hist_btn/need_two/no_history 等 en/zh 全量平移 Gradio _I18N。

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] Diff 选择与结果显示与旧页行为一致(候选仅成功 cell,run 后自动更新)
- [ ] 历史刷新与空态文案一致
- [ ] en/zh i18n 完整
- [ ] npm lint + build、ruff、定向 pytest 通过
