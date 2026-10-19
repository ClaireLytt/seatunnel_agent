# 批次结果报告:Change Impact Analysis React 迁移(2026-10-19)

## 批准依据

> grilling 三问(整套沿用 data_lineage 先例 / 流程分支同上 / GraphView 复用 +
> 2 票 + lineage 包清零 Gradio)用户回复:"yes";随后用户以 `/implement-spec`
> 启动实现。分支约束(用户原话):"就在现在的分支开发不允许切换新分支"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票 01:/impact 响应可加字段 mermaid(severity 图)+ sql_diff(粘贴模式)、白名单前置+结构化 bad_dir(+3 API 测试);React workspace(双页签、共享方言/深度、GraphView 去 onNode);cutover 退役 ui_impact.py 与 Gradio-only mermaid_html 模板(lineage 包零 Gradio) | data_lineage/{api,render,__init__,manifest}.py、frontend/change_impact/、tests/test_lineage_impact.py、tests/test_data_lineage.py | 8ea9626 |
| 高 | 票 02:页测 9 例(IMP1-IMP8 等价)+ i18n parity;删 impact.yaml/SCR3、清 catalog/page.py/css.py(.st-imp-* 零残留,settings 半边保留)/asserts.py | tests/test_impact_page.py、tests/test_impact_i18n.py、ui_testing/*、hub/css.py | (本报告同批 commit) |
| 中 | spec 与 2 张票 | .scratch/impact-react/ | 4556ce2 |

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 115 source files
pytest -q              -> 3219 passed, 1 skipped, 137 deselected in 114.83s
pytest tests/test_lineage_impact.py -> 50 passed(含 3 条新 mermaid/sql_diff/bad_dir 测试)
pytest -m uitest tests/test_impact_page.py -> 9 passed in 41.08s
npm run lint --workspace change_impact  -> 通过(无输出)
npm run build --workspace change_impact -> ✓ built in 51.89s
uitest smoke (--no-llm) -> PASS 36 · FAIL 0 · ERROR 0 · SKIP 0 · MANUAL 0 · 耗时 132s
                           报告: runs/20261019_063659/report.html
                           (39→36:IMP/SCR3 smoke YAML 退役,等价覆盖移入页测)
python scripts/check_workflow.py -> [PASS] AI 署名 / [PASS] 工作区干净 / [PASS] 报告落盘(全 PASS)
```

手工验证:hub 启动后 `GET /impact/` 200、`GET /lineage/` 200;
中文目录模式往返截图(severity 着色图 error/warn/info/blast + 分级报告)见下。

## 前后差异

- 测试:3214 → 3219 passed(+3 API、+4 parity 等),0 失败。YAML IMP1-IMP8/
  SCR3 → 页测 9 例等价。
- API:/impact 响应新增可加字段 mermaid(恒有)与 sql_diff(text 模式);
  坏目录由泛化 400 文本变为白名单前置 + 结构化 {code:"bad_dir",path}。
- 行为差异(1:1 例外,已记录):history 记录 source 标签由 "ui" 变 "api"
  (React 页经 REST 调用);Gradio 版 UI 端 is_dir 无白名单,REST 版白名单
  生效(默认 cwd,安全增强)。
- UI 截图(before = Gradio,after = React):
  - docs/reports/shots/impact-gradio-before-zh-light.png → impact-react-zh-report.png
  - docs/reports/shots/impact-gradio-before-en-dark.png → impact-react-en-dark.png
  - 全套 9 张在 .scratch/impact-react/screenshots/

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | GraphView/ReportView 已在 change_impact 与 data_lineage 两份拷贝 | frontend/*/components | per-workspace 模式 | 维护噪音 | 与 api.ts post/ApiError 一起收敛到 @shared(多批遗留) |
| 低 | hub include_router 拷贝模式(本批未新增,lineage router 复用) | hub/ui.py | 文档先例 | 同前 | registry 驱动统一挂载 |

## 未执行的步骤

- 无。

## Code-review fix-up(同批次追加)

双轴 code-review(Standards/Spec,范围 4556ce2..HEAD):**零硬违规**。修复:

| 发现 | 修复 |
| --- | --- |
| /impact 泛化失败 detail 为中文文本,英文用户见混语 | 结构化 {code:"analyze_failed",error:原始异常},前端套本地化 fail 模板(旧页语义);既有回归测试同步改断言 |
| 守卫文案含 markdown(**/反引号)但通知槽纯文本直显 | 通知槽改 ReportView 渲染(旧页 gr.Markdown 同款) |
| App.tsx 硬拷贝 SQL_DIALECTS 会随后端静默漂移 | 新增 parity 测试钉死 TS 列表 == sqlglot_lineage.SQL_DIALECTS |
| ui.ts 死导出(smallBtnCls/downloadText)、settings_ui.py 过时 .st-imp 注释 | 删除/更正 |

未修复的判断项:bad_dir 载荷 {code,path} 与 spec 文字 {code,message} 之差
(实现更优——客户端本地化,与历批同形);marked 渲染无 sanitizer 为全部
workspace 共性(ReportView 注释"trusted markdown"对粘贴 SQL 场景偏乐观),
建议统一在 @shared 引入 DOMPurify——记入遗留清单。

```
ruff check src tests -> All checks passed!
mypy                 -> Success: no issues found in 115 source files
pytest(impact 定向 55 条) -> 55 passed
pytest -m uitest tests/test_impact_page.py -> 9 passed
npm run lint/build --workspace change_impact -> 通过 / ✓ built
```
