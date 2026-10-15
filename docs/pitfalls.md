# 踩坑记录(pitfalls)

同类错误出现 ≥2 次时,必须在此追加一行:问题现象、根因、证据、规避方法。动手前先查本表。

| 日期 | 问题现象 | 根因 | 证据 | 规避方法 |
| --- | --- | --- | --- | --- |
| 2026-10-15 | Windows 下用 shell heredoc 写文件,中文字符损坏、反斜杠被剥离(即使加引号) | Windows shell 对 heredoc 的编码/转义处理与 POSIX 不一致 | 经验记录 | 写含中文或反斜杠的文件一律用编辑器/Write 工具,不用 heredoc;脚本 stdout 显式包成 UTF-8 |
| 2026-10-15 | Gradio 隐藏 textbox 在真实浏览器提交时值为 None,但 gradio_client 测试通过 | 真实浏览器不提交 hidden 组件的值,gradio_client 走的是 API 路径,绕过了前端行为 | 经验记录 | UI 行为类 bug 必须用 Playwright/真实浏览器(uitest smoke 套件)验证,不能只靠 gradio_client |
| 2026-10-15 | Gradio 6 中 `js=` 返回值不会替换 fn 的 inputs;Dropdown choices 在 build 时固化;DownloadButton 对路径有 cwd/temp 限制 | Gradio 6 前后端数据流约定所致 | 经验记录 | 需要把前端值传给后端时用 cookie + `gr.Request`;动态选项用事件回调更新;下载文件放在 cwd 或系统临时目录 |
