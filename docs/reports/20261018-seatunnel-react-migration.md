# 批次结果报告：SeaTunnel Pipeline Builder React 迁移（tickets 01–08）（2026-10-18）

## 批准依据

> 规划链路批准：`.scratch/seatunnel-react-migration/spec.md` 与 `issues/01..08` 全部标记
> ready-for-agent，由协调者按 ticket 分派实现（本批 = ticket 08 退役 + ticket 07 遗留的
> 占位区 parity 恢复）。

## 已完成

整条迁移（基线 5b42cf0 → 本批收尾）：

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 01 走通骨架：React shell `/seatunnel` + meta API | frontend/seatunnel/、agents/data/seatunnel/api.py | eb17945 |
| 高 | 02 聊天回路：SSE 流式 + Stop 中断 | api.py、Chat.tsx | db91df9 |
| 高 | 03 侧边栏连接控件：mode/config/template + connect | App.tsx、api.py | cc56574 |
| 高 | 04 会话管理：新建/列表/载入/重命名/删除 + 持久化 | Sessions.tsx、api.py | 8444627 |
| 中 | 05 上传 + 演示模式 SSE + 模板填充 | api.py、Chat.tsx | 2823164 |
| 中 | 06 导出 zip 端点 + 侧边栏下载 | api.py、App.tsx | c2bf1eb |
| 中 | 07 i18n 全量 parity + 暗色模式 | i18n.ts、tests/test_seatunnel_i18n.py | e4225c8 |
| 中 | 08a parity 恢复：空聊天占位区（ST logo、标题、3 个提示卡点击填充输入框、Docs 链接），移植 placeholder_hint1-3 键 | Chat.tsx、i18n.ts、tests/test_seatunnel_page.py | 28a2e3e |
| 高 | 08b 退役：删除 ui.py，格式化器/_I18N/演示脚本/EventCollector 抽到非 Gradio 的 rendering.py；hub/ui.py 去再导出与 sidebar_resize；css.py 剪除仅 seatunnel 的规则；剪除死 i18n 键；修 test_session_scope/test_ui_format 等 | rendering.py、hub/ui.py、hub/css.py、tests/* | bb7cf95 |
| 低 | 前后截图 + pitfalls 记录 | docs/reports/shots/、docs/pitfalls.md | 9d5551f、bb7cf95、03e2c85 |

### 08a 跳过的死键（证据）

旧页 `_I18N` 中 `quick_start`、`ex1-3`、`ex1_fill-ex3_fill`、`clear`、`chat_placeholder`、
`delete_session`、`settings_label` 定义后无任何控件引用（grep ui.py 仅见字典定义行
103-111/124-126/157-165/178-180；提示卡实际使用的是 `placeholder_hint1-3`，ui.py:694-696，
点击填充行为在 ui.py:1200-1217 的事件委托 JS）。故仅恢复 `placeholder_hint1-3` 与 Docs
链接；"快捷示例 chips" 即提示卡本身，"清空按钮"（clear 键）在旧页为死键，不予重建。

### 08b 核对过的 no-op（迁移清单验证）

- ui_testing catalog.py 无 seatunnel 条目；page.py READY 无 `/seatunnel`；无 YAML 用例引用
  `/seatunnel`（grep 均为 0 命中，仅 mcp.yaml/settings.yaml 的无关文案）。
- test_registry `_DATA_API_NAMES` 不含 seatunnel（路由无条件挂载，同 sql_review）——保持不变。
- css.py 剪除时逐类 grep 验证：`st-chatbot`（orchestrator 用）、`st-empty-*`/`st-hint-card`
  （text2sql ui_format 用）、`st-connect-btn`/`st-sidebar-control`/`st-topbar-*`/`st-home-btn`
  （data_comparison 用）均保留；仅删 0 引用的 `st-input*`、`st-btn-send/stop/upload/demo`、
  `st-docs-link`、`st-new-chat-btn`、`st-action-row/btn`、`st-rename-*`、`st-history-dd`、
  `st-delete-btn`、`st-sidebar-toggle/open-btn`。

## 验证结果

全部在本工作树执行（PYTHONPATH 指向工作树 src）：

```
ruff check src tests                          -> All checks passed!
mypy                                          -> Success: no issues found in 103 source files
pytest -q（全量）                              -> 2995 passed, 1 skipped, 104 deselected, 2 warnings in 153.40s
pytest -m uitest tests/test_seatunnel_page.py -> 5 passed in 24.65s（含新增提示卡填充用例）
python -m ...ui_testing run --suite smoke --no-llm
                                              -> PASS 83 · FAIL 0 · ERROR 0 · SKIP 2 · MANUAL 4 · 耗时 448s
                                                 报告: runs/20261018_015306/report.html
npm run lint --workspace seatunnel            -> eslint src（无输出，通过）
npm run build --workspace seatunnel           -> ✓ built in 3.12s
python scripts/check_workflow.py              -> 三项全 PASS（见附录）
```

## 前后差异

- 测试：基线（e4225c8）全量 pytest 约 2902 passed → 本批 2995 passed, 1 skipped（新增
  seatunnel api/page/i18n 用例，删除 Gradio 专属 export/normalize/template 用例）。
- UI 截图：
  - 旧 Gradio 页（commit 5b42cf0 worktree 起服务，wait_until="load"）：
    docs/reports/shots/seatunnel-gradio-before-{light,dark,zh}-full.png
  - 新 React 页：docs/reports/shots/seatunnel-react-{light,dark}-{full,chat,sidebar}.png、
    seatunnel-react-{light,dark}-zh-full.png（zh 全页可见恢复后的占位区：ST logo + 标题 +
    3 个提示卡 + Docs 链接，与 before 截图一致）。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | `config/t2s_examples.json` 测试运行后漂移，需人工还原 | 本批全量 pytest 后 `git status` 出现 M；pitfalls 2026-10-17/18 两行 | text2sql 示例库写回仓库内文件 | 易混入无关提交 | 加 fixture 把 `T2S_EXAMPLES_PATH` 重定向 tmp_path（测试隔离） |
| 低 | catalog.py AGENT_ROUTES 仍含 text2sql（React 页，引擎驱动 Gradio） | catalog.py:14 | 迁移时未同步 | uitest 引擎目录与现状不一致 | 用户圈选后单独清理 |
| 低 | rendering.py 未纳入 mypy files 白名单 | pyproject [tool.mypy] files 无 agents/data/seatunnel | 渐进式 typing 策略 | 该模块不受 mypy 门禁 | 后续补注解后加入白名单 |

## 未执行的步骤

- 旧页"before"截图仅截空态三张（light/dark/zh），未截旧页聊天过程态：旧页需真实 LLM 才有
  完整会话，demo 态已由 React 截图覆盖，收益低。
- 其余步骤均已执行。

## 附录：check_workflow 输出

```
[PASS] AI 署名: 无 AI 署名(范围 HEAD~10..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 无远端分支,跳过报告落盘检查
```

（预告的 "main 既有 Dependabot 提交触发署名 FAIL" 误报本次未出现：脚本只检查
HEAD~10..HEAD，该范围均为迁移分支提交，已逐一核对无署名行。）
