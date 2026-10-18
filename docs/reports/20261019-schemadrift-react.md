# 批次结果报告:Schema Drift Check React 迁移(2026-10-19)

## 批准依据

> grilling 三问(整套沿用模式 / 流程分支同上 / 缺口与规模预案)用户回复:
> "yes";随后用户以"yes"批准开始实现(批次 1)。
> 分支约束(用户原话):"就在现在的分支开发不允许切换新分支"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票 01:React workspace(方言下拉、双 DDL、目录折叠区 demo 预填 → Markdown 报告)、bad_path 结构化对齐、cutover、删 Gradio ui.py、_DATA_API_NAMES 移除 | frontend/schema_drift/、schema_drift/{api,manifest}.py、hub/ui.py、tests/test_registry.py | da904f0 |
| 高 | 票 02:页测 8 例(SDF1-SDF6 等价 + 空输入 + smoke)+ i18n parity(含方言列表与 demo 预填钉定);删 cases/schemadrift.yaml;清 page.py `.st-sdf-main` | tests/test_schemadrift_page.py、tests/test_schemadrift_i18n.py、ui_testing/page.py | (本报告同批 commit) |
| 中 | spec 与 2 张票 | .scratch/schemadrift-react/ | 0e40be1 |

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 115 source files
pytest -q              -> 3226 passed, 1 skipped, 143 deselected in 133.55s
pytest -m uitest tests/test_schemadrift_page.py -> 8 passed in 23.40s
npm run lint --workspace schema_drift  -> 通过(无输出)
npm run build --workspace schema_drift -> ✓ built in 3.06s
uitest smoke (--no-llm) -> PASS 34 · FAIL 0 · ERROR 0 · SKIP 0 · MANUAL 0 · 耗时 127s
                           报告: runs/20261019_075618/report.html
                           (36→34:SDF1/SDF2 smoke YAML 退役,等价覆盖移入页测)
python scripts/check_workflow.py -> (报告落盘提交后补记,见文末)
```

手工验证:hub 启动后 `GET /schemadrift/` 200;中文目录 demo 对比往返截图
(破坏 3 / 风险 2 / 提示 3 分级报告)见下。

## 前后差异

- 测试:3219 → 3226 passed(+7 parity),0 失败。YAML SDF1-SDF6 → 页测
  8 例等价。
- API:成功契约不变;坏路径 detail 由文本 `路径不存在: {raw}` 变为结构化
  `{code:"bad_path",path}`(既定迁移模式,前端本地化)。
- UI 截图(before = Gradio,after = React):
  - docs/reports/shots/schemadrift-gradio-before-zh-light.png → schemadrift-react-zh-report.png
  - docs/reports/shots/schemadrift-gradio-before-en-dark.png → schemadrift-react-en-dark.png
  - 全套 9 张在 .scratch/schemadrift-react/screenshots/

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | manifest 卡片色 #2563eb(蓝)与"禁蓝紫"UI 规范存在张力 | manifest.py color | 迁移不触碰 manifest 视觉字段(精准修改,sql_fmt 批同类遗留) | 仅 hub 卡片一处 | 等用户决定是否换色 |
| 低 | GraphView/ReportView/api.ts 跨 workspace 拷贝持续累积 | frontend/*/ | per-workspace 模式 | 维护噪音 | 统一收敛到 @shared(多批遗留) |

## 未执行的步骤

- 无。
