# 批次结果报告:Metric Consistency Check React 迁移(2026-10-19)

## 批准依据

> grilling 三问(整套沿用模式 / 流程分支同上 / 缺口与规模预案)用户回复:
> "yes";随后用户以 `/implement-spec` 启动实现。
> 分支约束(用户原话):"就在现在的分支开发不允许切换新分支"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票 01:React workspace(目录输入 demo 预填、方言下拉 → 冲突报告)、bad_dir/check_failed 结构化、cutover、删 Gradio ui.py、_DATA_API_NAMES 移除 | frontend/metric_diff/、metric_diff/{api,manifest}.py、hub/ui.py、tests/test_registry.py | (见 git log 票 01) |
| 高 | 票 02:页测 5 例(MDF1-MDF5 等价 + 空目录)+ i18n parity(方言/demo 预填钉定);删 cases/metricdiff.yaml;清 page.py `.st-mdf-main`;内置用例下限 55→50 | tests/test_metricdiff_page.py、tests/test_metricdiff_i18n.py、ui_testing/page.py、tests/test_ui_testing.py | (本报告同批 commit) |
| 中 | spec 与 2 张票 | .scratch/metricdiff-react/ | 80af4ae |

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 114 source files
pytest -q              -> 3232 passed, 1 skipped, 146 deselected in 132.68s
pytest tests/test_metric_diff.py -> 23 passed
pytest -m uitest tests/test_metricdiff_page.py -> 5 passed in 15.32s
npm run lint --workspace metric_diff  -> 通过(无输出)
npm run build --workspace metric_diff -> ✓ built in 3.11s
uitest smoke (--no-llm) -> PASS 32 · FAIL 0 · ERROR 0 · SKIP 0 · MANUAL 0 · 耗时 118s
                           报告: runs/20261019_085853/report.html
                           (34→32:MDF1/MDF2 smoke YAML 退役,等价覆盖移入页测)
python scripts/check_workflow.py -> [PASS] AI 署名 / [PASS] 工作区干净 / [PASS] 报告落盘(全 PASS)
```

手工验证:hub 启动后 `GET /metricdiff/` 200;中文 demo 往返截图(gmv 公式
冲突 ⛔ + contact 来源冲突 ⚠️)见下。

## 前后差异

- 测试:3226 → 3232 passed(+7 parity 等),0 失败。YAML MDF1-MDF5 → 页测
  5 例等价。
- API:成功契约不变;坏目录由 require_dir 文本 400 变为白名单前置 +
  结构化 {code:"bad_dir",path};检查异常结构化降级 {code:"check_failed"}。
- UI 截图(before = Gradio,after = React):
  - docs/reports/shots/metricdiff-gradio-before-zh-light.png → metricdiff-react-zh-report.png
  - docs/reports/shots/metricdiff-gradio-before-en-dark.png → metricdiff-react-en-dark.png
  - 全套 9 张在 .scratch/metricdiff-react/screenshots/

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | manifest 卡片色 #9333ea(紫)与"禁蓝紫"UI 规范存在张力 | manifest.py color | 迁移不触碰 manifest 视觉字段(精准修改,sql_fmt/schemadrift 同类遗留) | 仅 hub 卡片一处 | 等用户决定是否统一换色 |
| 低 | ReportView/api.ts 跨 workspace 拷贝持续累积 | frontend/*/ | per-workspace 模式 | 维护噪音 | @shared 收敛(多批遗留) |

## 未执行的步骤

- 无。
