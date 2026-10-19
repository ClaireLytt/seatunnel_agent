# 批次结果报告:SQL Dialect Translation React 迁移(2026-10-19)

## 批准依据

> grilling 六问(整套沿用前两批模式 / 流程与分支同上 / REST 缺口补薄层 /
> POST /advice 薄包装 / batch out_dir 取 A 方案双向白名单 / 桥接与 ConfView
> 先例件)用户回复:"yes";随后用户以 `/implement-spec` 启动实现。
> 分支约束(用户原话):"就在现在的分支开发不允许切换新分支"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票 01:POST /advice(结构化 none/no_key/error/ok,永不 500)、/batch 可选 out_dir(读写同白名单)+ 结构化 bad_dir、React workspace(双栏、方言对下拉、SqlView 复制块、建议折叠区、localStorage 桥 pickup)、cutover、删 ui.py、_DATA_API_NAMES 移除、前后截图 | src/seatunnel_agent/agents/data/sql_transpile/、frontend/sql_transpile/、src/seatunnel_agent/hub/ui.py、tests/test_sql_transpile.py、tests/test_registry.py | 7ed9410 |
| 高 | 票 02:Playwright 页测 11 例(TRP1-TRP9 等价 + advice 确定性路径 + 桥接 pickup)+ i18n parity;/batch 加 report 旗标;删 transpile.yaml 与 scroll.yaml SCR2;清 catalog transpile 条目与 page.py READY/.st-trp-* 选择器 | tests/test_transpile_page.py、tests/test_transpile_i18n.py、ui_testing/catalog.py、ui_testing/page.py | (本报告同批 commit) |
| 中 | spec 与票据 | .scratch/transpile-react/ | ef43391 |

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 115 source files
pytest -q              -> 3176 passed, 1 skipped, 111 deselected in 114.88s
pytest tests/test_sql_transpile.py -> 69 passed(含 5 条新 advice/out_dir API 测试)
pytest -m uitest tests/test_transpile_page.py -> 11 passed in 37.91s
npm run lint --workspace sql_transpile  -> 通过(无输出)
npm run build --workspace sql_transpile -> ✓ built in 2.95s
uitest smoke (--no-llm) -> PASS 50 · FAIL 0 · ERROR 0 · SKIP 0 · MANUAL 1 · 耗时 197s
                           报告: runs/20261019_010126/report.html
                           (53→50:TRP1/TRP2/SCR2 smoke YAML 退役,等价覆盖移入页测)
python scripts/check_workflow.py -> [PASS] AI 署名 / [PASS] 工作区干净 / [PASS] 报告落盘(全 PASS)
```

手工验证:hub 启动后 `GET /transpile/` 200;
`POST /api/transpile/batch`(dir=no/such/dir)返回 `{"code":"bad_dir",...}`;
中文翻译往返截图(JSON_EXTRACT、全自动 1)见下。

## 前后差异

- 测试:3166 → 3176 passed(+5 API 测试、+4 parity、+1 其他;页测 11 例在
  uitest 标记下另计),0 失败。YAML TRP1-TRP9/SCR2 → 页测等价覆盖
  (TRP6 LLM 用例改为确定性 none 路径,真 LLM 质量不进自动化)。
- API:新增 `POST /advice`;`/batch` 新增可选 `out_dir`(双向白名单)与
  `report` 旗标;坏目录 detail 由 `目录不存在: {dir}` 文本变为结构化
  `{code,path}`(conflint/sqlfmt 同形状);既有 inline 契约不变。
- UI 截图(before = Gradio,after = React):
  - docs/reports/shots/transpile-gradio-before-zh-light.png → transpile-react-zh-report.png
  - docs/reports/shots/transpile-gradio-before-en-dark.png → transpile-react-en-dark.png
  - 全套 9 张在 .scratch/transpile-react/screenshots/

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | /batch 坏目录 detail 文本→结构化,解析旧文本的外部脚本需适配 | api.py 票 01 diff | 前端本地化需要(先例同形状) | 未发现外部消费者 | 保持现状 |
| 低 | /advice 为 LLM 端点,公网部署时可能被滥用刷 token | api.py advice_endpoint | 1:1 保住页面功能 | 仅在配置了 key 的部署暴露 | 如需要可加限流/auth(--api 的 key 机制) |
| 低 | hub include_router 已第 8 份拷贝 | hub/ui.py | 触点清单第 4 点即此模式 | 维护噪音 | 未来统一改 registry 驱动挂载 |

## 未执行的步骤

- 无。

## Code-review fix-up(同批次追加)

双轴 code-review(Standards/Spec,范围 11b86ad..HEAD)后的修复:

| 发现 | 修复 |
| --- | --- |
| hub/css.py 残留 `.st-trp-*` 死选择器 6 处(触点清单第 7 点,硬违规) | 全部移除(lineage/impact/settings 选择器保留) |
| /advice error 状态把原始异常文本回给未认证客户端,可能泄露内部信息 | detail 改为泛化消息 `LLM advice failed (<Type>)`,详情只进服务端日志 |
| 全失败脚本时 React 仍显示 `-- transpile-error` 译文块,旧页为隐藏 | 前端按 `statements.some(ok)` 门控,恢复 1:1 |

未修复的判断项(有先例/文档依据):api.ts post/ApiError 第 4 份拷贝(既有
per-workspace 模式,收敛到 @shared 留待统一重构)、/translate /batch 的
report 旗标与 /advice error 状态(向后兼容的必要扩展,spec 故事 8 允许)、
i18n 冷启动读 cookie(sql_fmt 先例,切语言经刷新生效)、advice_none/no_key
去掉 markdown 斜体包裹(parity 测试已注明)。

```
ruff check src tests -> All checks passed!
mypy                 -> Success: no issues found in 115 source files
pytest(定向 85 条)   -> 85 passed
pytest -m uitest tests/test_transpile_page.py -> 11 passed
npm run build --workspace sql_transpile -> ✓ built
```
