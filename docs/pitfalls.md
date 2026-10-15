# 踩坑记录(pitfalls)

同类错误出现 ≥2 次时,必须在此追加一行:问题现象、根因、证据、规避方法。动手前先查本表。

| 日期 | 问题现象 | 根因 | 证据 | 规避方法 |
| --- | --- | --- | --- | --- |
| 2026-10-15 | Windows 下用 shell heredoc 写文件,中文字符损坏、反斜杠被剥离(即使加引号) | Windows shell 对 heredoc 的编码/转义处理与 POSIX 不一致 | 经验记录 | 写含中文或反斜杠的文件一律用编辑器/Write 工具,不用 heredoc;脚本 stdout 显式包成 UTF-8 |
| 2026-10-15 | Gradio 隐藏 textbox 在真实浏览器提交时值为 None,但 gradio_client 测试通过 | 真实浏览器不提交 hidden 组件的值,gradio_client 走的是 API 路径,绕过了前端行为 | 经验记录 | UI 行为类 bug 必须用 Playwright/真实浏览器(uitest smoke 套件)验证,不能只靠 gradio_client。两处疑似同型实例已于 2026-10-15 用真实浏览器逐一验证:(1) text2sql `/history` 行选择(`ui.py` `#hist-sel-idx`):功能正常,但走的是 `history_table.select` 原生事件路径(点击单元格 → "Selected row #0" + 详情 SQL 渲染,见 `runs/adhoc/t2s_hist/debug3_after_click.png`);隐藏 textbox + 行点击 JS 路径在 Gradio 6 下是**死代码**——`visible=False` 的 Textbox 根本不挂载 DOM(`querySelector('#hist-sel-idx …')` 为 null),且 Dataframe 可见网格已不是 `table tbody tr`,JS 只绑到隐藏的测量行上,写值是静默 no-op,不触发也不致错(行高亮 `.st-row-selected` 因此从不生效,但 Gradio 自带单元格选中高亮兜底)。(2) data_comparison 查看报告(`ui.py` `dc-hidden-report`):功能正常,pitfall 不适用——数据流是后端 output → 前端组件 store → `.then(js=...)` 读 store 值新开标签页,不依赖浏览器"提交" hidden 组件;adhoc 实测弹出页含完整报告("数据比对报告/行数 10 vs 9",见 `runs/adhoc/dc_view_report/`)。结论:该坑只命中"前端 JS 改 DOM 值→期望后端收到"的方向;后端→前端 js 读值方向安全;Gradio 6 下 hidden 组件甚至不在 DOM 中,JS 直改 DOM 的 workaround 整体失效,传值一律用 cookie + `gr.Request` 或可见组件 |
| 2026-10-15 | Gradio 6 中 `js=` 返回值不会替换 fn 的 inputs;Dropdown choices 在 build 时固化;DownloadButton 对路径有 cwd/temp 限制 | Gradio 6 前后端数据流约定所致 | 经验记录 | 需要把前端值传给后端时用 cookie + `gr.Request`;动态选项用事件回调更新;下载文件放在 cwd 或系统临时目录 |
| 2026-10-15 | AI 代理提交 commit 时误加 `Co-Authored-By: Claude ...` 署名,同日发生 2 次(validator 修复、ruff 规则 commit),均事后 amend 移除 | 代理运行环境默认附加 AI 署名,与本项目 CLAUDE.md 第 1 节"不添加 AI 署名"冲突,代理首次提交时未复核 | 2026-10-15 两个子任务汇报中的 amend 记录(最终 hash 0793415、2f23203 均已无署名) | 每次 commit 前在提交信息中显式不含署名行;提交后用 `git log -1 --format=%B` 复核;发现即 amend |
| 2026-10-15 | 子代理只给进度汇报,未按阶段二第 6 步交付固定格式的结果报告 | 结果报告的格式和"每次修改后必须交付"当时未写入 CLAUDE.md,仅存在于口头需求 | 2026-10-15 批次 1-3 的汇报形式 | 已将结果报告固定格式(已完成/验证结果/前后差异/未解决问题)写入 CLAUDE.md 第 7 节;每次代码修改验证完成后必须立即交付 |
