# 批次结果报告:Test Data Generator React 迁移(2026-10-19)

## 批准依据

> grilling 四问(整套沿用模式 / 流程分支同上 / 缺口与规模预案 /
> markdown 报告 + 2 票)用户回复:"yes";随后用户以 `/implement-spec`
> 启动实现。分支约束(用户原话):"就在现在的分支开发不允许切换新分支"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票 01:React workspace(demo 预填、DDL、7 方言、行数滑杆 1-50、SQLite 验证勾选 → Markdown 报告)、cutover、删 Gradio ui.py、_DATA_API_NAMES 移除;后端零改动 | frontend/sql_testgen/、manifest.py、hub/ui.py、tests/test_registry.py | 7bb5f5f |
| 高 | 票 02:Playwright 页测 8 例(TGN1-TGN6 等价 + 空 SQL + smoke)+ i18n parity(含 demo 预填钉定);删 cases/testgen.yaml;清 page.py `.st-tgn-main` | tests/test_testgen_page.py、tests/test_testgen_i18n.py、ui_testing/page.py | (本报告同批 commit) |
| 中 | spec 与 2 张票 | .scratch/testgen-react/ | 5a3a37f |

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 115 source files
pytest -q              -> 3199 passed, 1 skipped, 123 deselected in 116.48s
pytest -m uitest tests/test_testgen_page.py -> 8 passed in 27.24s
npm run lint --workspace sql_testgen  -> 通过(无输出)
npm run build --workspace sql_testgen -> ✓ built in 3.25s
uitest smoke (--no-llm) -> PASS 42 · FAIL 0 · ERROR 0 · SKIP 0 · MANUAL 1 · 耗时 164s
                           报告: runs/20261019_023021/report.html
                           (44→42:TGN1/TGN2 smoke YAML 退役,等价覆盖移入页测)
python scripts/check_workflow.py -> (报告落盘提交后补记,见文末)
```

手工验证:hub 启动后 `GET /testgen/` 200;中文往返截图(demo JOIN 生成双表
CSV + SQLite 验证 ✅)见下。

## 前后差异

- 测试:3194 → 3199 passed(+5 parity),0 失败。YAML TGN1-TGN6 → 页测
  8 例等价。后端零改动(`/generate`、`/health` 契约原样,既有 API 测试通过)。
- UI 截图(before = Gradio,after = React):
  - docs/reports/shots/testgen-gradio-before-zh-light.png → testgen-react-zh-report.png
  - docs/reports/shots/testgen-gradio-before-en-dark.png → testgen-react-en-dark.png
  - 全套 9 张在 .scratch/testgen-react/screenshots/

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | hub include_router 已第 10 份拷贝 | hub/ui.py | 文档先例模式 | 维护噪音 | 未来 registry 驱动统一挂载(多批重复遗留,建议尽快排期) |

## 未执行的步骤

- 无。
