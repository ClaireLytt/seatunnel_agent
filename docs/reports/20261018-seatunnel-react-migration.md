# 批次结果报告：SeaTunnel Pipeline Builder React 迁移（tickets 01–08）（2026-10-18）

## 批准依据

用户批准原话（逐字引用）：

- 对提出 4 批次迁移方案的 grilling 轮，用户回答：「yes」。
- 随后用户依次调用斜杠命令：「/to-spec」、「/to-tickets」、「/implement-spec」，
  即批准规划链路产物（`.scratch/seatunnel-react-migration/spec.md` 与 `issues/01..08`，
  全部标记 ready-for-agent）并授权按 ticket 分派实现（本批 = ticket 08 退役 +
  ticket 07 遗留的占位区 parity 恢复）。

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

## 修正批（code-review 跟进，2026-10-18）

评审发现 → 处理结果（S=标准项，P=规格项）：

| 项 | 结论 | 处理 / 证据 |
| --- | --- | --- |
| S1 api.py `_MSG`/`_MODES` 与 rendering 重复 | 已修 | api.py 删除两份本地副本，改用 `rendering.translate` + `I18N` mode_*/no_settings/stopped 键；删除"页面稍后退役"过期注释 |
| S2 rendering._I18N 保留仅 parity 测试消费的 UI-chrome 键 | 已修 | rendering.I18N 只留后端渲染键（mode_*、no_settings、stopped、demo_*_done）；旧页措辞以内联字面量移入 tests/test_seatunnel_i18n.py（parity 真值随之移入测试，文件头有注明），新增 test_backend_i18n_holds_only_backend_rendered_keys 锁定键集 |
| S3 Chat.tsx 流冲洗三元重复 + ▌ 永久残留 | 已修 | 抽出 `flushStream` helper；确认 ▌ 残留为真（旧页 formatter ui.py:415 同样把 " ▌" 烙进冲洗历史，属沿袭的渲染 bug）：Chat.tsx 冲洗不再带 ▌（光标只在实时气泡渲染期后缀），rendering.py `_flush_delta` 同步去掉，test_ui_format 断言改为 `"▌" not in` |
| S4 私有名跨模块引用 / 直接赋值 `agent._on_event` | 已修 | rendering 公有化：`I18N`/`translate`/`format_events_as_chat`/`DEMO_STEPS`/`DEMO_CONFIG`/`TOOL_EMOJI`（仓库内引用全部就地改名，无别名）；SeaTunnelAgent 新增最小公有 setter `set_event_callback`，api.py 改用之 |
| S5 upload 无大小上限 / _CONVERSATIONS 无界 | 已修 | upload 超 1 MB 返回 413（新增 test_upload_rejects_oversized_file）；`_get_conversation` 超过 100 条时逐出最旧的空闲会话（已完成轮次均已持久化到 history，无数据丢失） |
| P1 uitest smoke 未覆盖 /seatunnel | 误报（按设计排除，证据如下） | /seatunnel 在 Gradio 时代就从未进 catalog/用例（`git show 5b42cf0:...catalog.py` 无 seatunnel；全历史 `git log -S "/seatunnel" -- cases/` 零命中）。迁移先例即如此：aux_pages.yaml/extended.yaml/scroll.yaml 注释明确 React 页退出 YAML 用例、浏览器覆盖移入 pytest Playwright（react_migration.md 第 9-10 条）；/seatunnel 的真浏览器覆盖 = tests/test_seatunnel_page.py（5 passed）。smoke 仍整体重跑通过（见修正批验证） |
| P2 localStorage 跨页桥 | 误报（无桥） | `git show 5b42cf0:...seatunnel/ui.py \| grep -n localStorage` 零命中（st_ 前缀仅 CSS class 名）；旧页无跨页 localStorage 桥，无需恢复 |
| P3 批准引用非用户原话 | 已修 | 本报告"批准依据"改为逐字引用：「yes」+「/to-spec」「/to-tickets」「/implement-spec」 |
| P4 新后端模块未进 mypy 白名单 | 已修 | pyproject [tool.mypy] files 加入 agents/data/seatunnel/{api,rendering}.py；修复暴露的 1 处 arg-type（settings 判空收窄）→ mypy Success: no issues found in 105 source files |
| P5 i18n verbatim 覆盖缺口 | 已修 | test_seatunnel_i18n.py 内联字面量扩到 connected/connectFailed/templatePrompt/errorLabel/completedIn/docsLink；确认 errorLabel/completedIn 旧页双语言均为英文（ui.py:632-633 f-string 无语言分支）、newChat 的"+"落在按钮字形（Sessions.tsx，新增 test_new_chat_plus_glyph_lives_on_button 锁定）；upload/collapse/expand 旧页无文字（仅 +/☰ 字形），测试文件头已注明 |

### 修正批验证（PYTHONPATH=工作树 src）

```
ruff check src tests                          -> All checks passed!
mypy                                          -> Success: no issues found in 105 source files
pytest -q（全量）                              -> 2998 passed, 1 skipped, 104 deselected, 2 warnings in 136.63s
pytest -m uitest tests/test_seatunnel_page.py -> 5 passed in 26.59s
python -m ...ui_testing run --suite smoke --no-llm
                                              -> PASS 83 · FAIL 0 · ERROR 0 · SKIP 2 · MANUAL 4 · 耗时 447s
                                                 报告: runs/20261018_022433/report.html
npm run lint --workspace seatunnel            -> eslint src（无输出，通过）
npm run build --workspace seatunnel           -> ✓ built in 3.14s
python scripts/check_workflow.py              -> [PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘（三项全 PASS）
```

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | `config/t2s_examples.json` 测试运行后漂移，需人工还原 | 本批全量 pytest 后 `git status` 出现 M；pitfalls 2026-10-17/18 两行 | text2sql 示例库写回仓库内文件 | 易混入无关提交 | 加 fixture 把 `T2S_EXAMPLES_PATH` 重定向 tmp_path（测试隔离） |
| 低 | catalog.py AGENT_ROUTES 仍含 text2sql（React 页，引擎驱动 Gradio） | catalog.py:14 | 迁移时未同步 | uitest 引擎目录与现状不一致 | 用户圈选后单独清理 |

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
