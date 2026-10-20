# 03: 功能对齐——载入示例、校验、Recharts 趋势、i18n

**What to build:** 载入示例按钮(GET demo 填入编辑器);校验按钮(POST validate,ok/本地化错误,空套件提示);历史趋势折叠区(Recharts,数据 GET /history,先例 uitest CountsChart);en/zh 文案全量平移自 Gradio _I18N,随 st-lang cookie。完成后 1:1 验收清单全绿。

**Blocked by:** 02

**Status:** ready-for-agent

- [ ] 载入示例/校验按钮行为与 Gradio 一致(校验不调 LLM)
- [ ] 趋势图 Recharts 渲染 history 数据;无 runs 时显示 no_runs 文案
- [ ] en/zh i18n 完整
- [ ] npm lint + build、ruff、定向 pytest 通过
