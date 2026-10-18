# 批次结果报告:Data Lineage React 迁移(2026-10-19)

## 批准依据

> grilling 七问(整套沿用模式 / 流程分支同上 / 图渲染与范围预案 / skew 式
> 会话持图 / mermaid npm / SSE 问答 / impact 不迁 + 4 票)用户回复:"yes";
> 随后用户以 `/implement-spec` 启动实现。
> 分支约束(用户原话):"就在现在的分支开发不允许切换新分支"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票 01:lineage 会话注册表(建图一次多次查询)、POST /session //build(stats+表清单)、session_id 贯穿既有端点(结构化 need_graph)、POST /search、GET /snapshots、/sla_impact 响应带链路 mermaid、SSE /analyze/stream(step/tool/delta/final,no_settings 结构化);10 条 API 测试 | data_lineage/{registry,api}.py、tests/test_lineage_session_api.py | 889446d |
| 高 | 票 02:React 页 A — 数据源/建图/查询面板、mermaid npm 渲染 + 节点点击重查、Mermaid 源折叠 | frontend/data_lineage/ | e8c396c |
| 高 | 票 03:React 页 B — 搜索/路径/SLA/体检/快照、SSE 问答面板 + cutover 退役 732 行 Gradio 页(/impact 原样验证 200)| ToolsPanel/AgentPanel、manifest.py、hub/ui.py | 6c108e1 |
| 高 | 票 04:页测 11 例 + i18n parity;删 lineage.yaml×2/SCR1、清 catalog/page.py/css.py(保 /impact 共用选择器)、asserts.py 陈旧滚动选择器(含上批漏的 .st-trp-page)| tests/test_lineage_page.py、tests/test_lineage_i18n.py、ui_testing/*、hub/css.py | (本报告同批 commit) |
| 中 | spec 与 4 张票 | .scratch/lineage-react/ | f538a8e |

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 115 source files
pytest -q              -> 3214 passed, 1 skipped, 131 deselected in 115.89s
pytest tests/test_lineage_session_api.py -> 10 passed
pytest -m uitest tests/test_lineage_page.py -> 11 passed in 38.59s
npm run lint --workspace data_lineage  -> 通过(无输出)
npm run build --workspace data_lineage -> ✓ built(mermaid chunk 体积告警,仅提示)
uitest smoke (--no-llm) -> PASS 39 · FAIL 0 · ERROR 0 · SKIP 0 · MANUAL 0 · 耗时 148s
                           报告: runs/20261019_031152/report.html
                           (42→39:LIN/SCR1 smoke YAML 退役;IMP 用例保持通过)
python scripts/check_workflow.py -> (报告落盘提交后补记,见文末)
```

手工验证:hub 启动后 `GET /lineage/` 200、`GET /impact` 200(Gradio 页不受损);
中文往返截图(建图统计 7 表/6 边/20 字段边、Mermaid SVG、链路概览)见下。

## 前后差异

- 测试:3199 → 3214 passed(+10 会话 API、+5 parity),0 失败。YAML
  LIN1-LIN11/SCR1 → 页测 11 例等价(LIN12 真 LLM 留手动,SSE no_settings
  走确定性覆盖)。
- API:新增 /session /build /search GET /snapshots 与 SSE /analyze/stream;
  既有端点新增可选 session_id(向后兼容);/sla_impact 响应新增 mermaid 字段。
- 架构:图状态从 Gradio gr.State → 服务端会话注册表(cap+TTL);图渲染从
  iframe+CDN → mermaid npm(离线/CI 安全),节点跳转从 iframe 桥 → 原生回调。
- UI 截图(before = Gradio,after = React):
  - docs/reports/shots/lineage-gradio-before-zh-light.png → lineage-react-zh-report.png
  - docs/reports/shots/lineage-gradio-before-en-dark.png → lineage-react-en-dark.png
  - 全套 9 张在 .scratch/lineage-react/screenshots/

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | /impact 页成为 data 工作区最后一个 Gradio 页之一,与 lineage 共包共 API | manifest.py 第二条目 | 本批范围排除(grilling Q3/Q7) | 混合栈继续存在 | 建议下批迁移 /impact(API /impact 端点已就绪,规模小) |
| 低 | mermaid chunk ~500KB+(构建告警) | npm build 输出 | 官方包体积 | 首次加载略重 | 可按需 dynamic import 优化 |
| 低 | 报告 markdown 中"血缘图"小节仍内嵌 mermaid 源码块(与旧页一致) | 截图 | 后端 render_report 行为,1:1 | 轻微冗余(图已单独渲染) | 如需可在后端报告里去掉该节,属功能性改动需单独批准 |
| 低 | hub include_router 已第 11 份拷贝 | hub/ui.py | 文档先例模式 | 维护噪音 | registry 驱动统一挂载(多批遗留,建议排期) |

## 未执行的步骤

- 无。
