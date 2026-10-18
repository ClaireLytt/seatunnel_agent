# 批次结果报告:SQL Formatter React 迁移(2026-10-19)

## 批准依据

> grilling 四问(整套沿用 Config Lint 模式 / 流程与分支同上批 / REST 缺口补薄层
> / 单端点加可选 dir + SQLFMT_API_ALLOWED_DIRS 白名单)用户回复:"yes";
> 随后用户以 `/implement-spec` 启动实现。
> 分支约束(用户原话):"就在现在的分支开发不允许切换新分支"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票 01:API 可选 dir(白名单前置+结构化 bad_dir+批量报告,向后兼容,4 条新 API 测试)、React workspace(7 方言下拉)、cutover、删 Gradio ui.py、_DATA_API_NAMES 移除、前后截图 | src/seatunnel_agent/agents/data/sql_fmt/、frontend/sql_fmt/、src/seatunnel_agent/hub/ui.py、tests/test_sql_fmt.py、tests/test_registry.py | dfd14b2 |
| 高 | 票 02:Playwright 页测 9 例(FMT1-FMT6 等价+空输入+bad_dir)+ i18n parity;删 cases/sqlfmt.yaml;清 page.py `.st-fmt-main` | tests/test_sqlfmt_page.py、tests/test_sqlfmt_i18n.py | (本报告同批 commit) |
| 中 | spec 与票据 | .scratch/sqlfmt-react/ | 82dcc96 |

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 115 source files
pytest -q              -> 3166 passed, 1 skipped, 103 deselected in 111.31s
pytest tests/test_sql_fmt.py -> 27 passed(含 4 条新 dir 分支 API 测试)
pytest -m uitest tests/test_sqlfmt_page.py -> 9 passed in 35.90s
npm run lint --workspace sql_fmt  -> 通过(无输出)
npm run build --workspace sql_fmt -> ✓ built in 3.07s
uitest smoke (--no-llm) -> PASS 53 · FAIL 0 · ERROR 0 · SKIP 0 · MANUAL 1 · 耗时 210s
                           报告: runs/20261019_002813/report.html
                           (55→53:FMT1/FMT2 smoke YAML 退役,等价覆盖移入页测)
python scripts/check_workflow.py -> [PASS] AI 署名 / [PASS] 工作区干净 / [PASS] 报告落盘(全 PASS)
```

手工验证:hub 启动后 `GET /sqlfmt/` 200;
`POST /api/sqlfmt/format`(dir=no/such/dir)返回 `{"code":"bad_dir",...}`;
中文格式化往返截图见下。

## 前后差异

- 测试:3158 → 3166 passed(+4 API dir 测试、+4 i18n parity;页测 9 例在
  uitest 标记下另计),0 失败。YAML FMT1-FMT6 → 页测等价 + 空输入/bad_dir。
- API:`POST /api/sqlfmt/format` 新增可选 `dir`(白名单 SQLFMT_API_ALLOWED_DIRS
  前置、结构化 bad_dir、只检查不写);原 inline sql 契约不变(27 条测试全过)。
- UI 截图(before = Gradio,after = React):
  - docs/reports/shots/sqlfmt-gradio-before-zh-light.png → sqlfmt-react-zh-report.png
  - docs/reports/shots/sqlfmt-gradio-before-en-dark.png → sqlfmt-react-en-dark.png
  - 全套 9 张在 .scratch/sqlfmt-react/screenshots/

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | FormatRequest.sql 由必填(min_length=1)改为可选,空 body 由 422 变 400 | api.py 票 01 diff | sql/dir 二选一需要 | 依赖 422 的外部调用(未发现)需适配 | 保持现状 |
| 低 | manifest 卡片色 #4f46e5(靛蓝)与"禁蓝紫"UI 规范存在张力 | manifest.py color | 迁移不触碰 manifest 视觉字段(精准修改) | 仅 hub 卡片一处 | 等用户决定是否换色 |

## 未执行的步骤

- 无。
