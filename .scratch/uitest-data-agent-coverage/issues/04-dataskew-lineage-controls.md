# 04: data_skew 与 data_lineage 控件补全 + 退役 LIN13

**What to build:** 数据倾斜页:分析模式下拉切换(llm 模式无 key 时的确定性降级提示)、split-key 的上传 conf 与下载 patched conf、Runtime 面板的服务端拉取与运行时文件上传、连接预设 load、采样大小下拉。血缘页:方向下拉切换为仅上游/仅下游并断言结果差异、Copy mermaid 源(剪贴板断言)、path 路径分析按钮、Agent 面板真实提问的确定性可达路径。同时删除 uitest `extended.yaml` 中指向已退役 Gradio /lineage 的 LIN13,方向过滤改由 Playwright 覆盖。

**Blocked by:** 01(下载与剪贴板断言模式)

**Status:** ready-for-agent

- [ ] data_skew:模式下拉切到 llm 后无 key 降级提示;split-key 上传 conf → 检查 → 下载 patched conf `expect_download` 真测
- [ ] data_skew:Runtime 面板 rt_btn 与文件上传各验一次;预设 load 与采样大小下拉切换后仍可 Verify
- [ ] data_lineage:方向=仅上游时结果含上游表且不含下游表(对等覆盖原 LIN13);仅下游对称验证
- [ ] data_lineage:Copy mermaid 源剪贴板断言;path 按钮点击出路径结果;Agent 提问确定性路径验证
- [ ] LIN13 自 extended.yaml 移除,uitest 套件仍全绿
- [ ] `pytest -m uitest -k "dataskew or lineage"` 通过;ruff/mypy 通过
