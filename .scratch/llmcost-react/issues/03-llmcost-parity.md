# 03: 功能对齐——两张 Recharts 图、价格表、CSV、i18n

**What to build:** ① 按日堆叠成本图:summary.by_day_model 按模型分色堆叠 Bar,budget>0 时画日均预算 ReferenceLine 虚线(budget_line 文案);② 按模型 tokens 图:by_model 的 input/output 堆叠;③ 价格表折叠区:GET /prices 表格(前缀/输入价/输出价/来源)+ price_note(含 override 路径);④ CSV 导出按钮:前端由 summary 生成 Blob(UTF-8 BOM,列对齐旧页 _csv_file);⑤ i18n:chart_cost/chart_tokens/budget_line/price_acc/price_note/csv_btn 等 en/zh 平移。图表配色用主题 token(先例 llm_eval TrendChart),禁蓝紫/渐变。

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] 两图语义与旧页 matplotlib 一致(堆叠+预算线;无数据不渲染图)
- [ ] 价格表含 deepseek-chat 行与 override 提示
- [ ] CSV 下载内容列结构对齐旧页
- [ ] en/zh i18n 完整;npm lint + build、ruff、定向 pytest 通过
