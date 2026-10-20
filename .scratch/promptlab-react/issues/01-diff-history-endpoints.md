# 01: 薄端点 diff + history(+ API 测试)

**What to build:** 客户端 POST 两段文本(+lang)得到与旧页逐字一致的 unified diff markdown(render_diff;相同文本返回 diff_same 文案);GET 取最近实验记录(ExperimentLogger.recent,preview 不含全文/密钥)。run/profiles/health 行为不变;runner/report/xlog 引擎零改动。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] diff 端点:不同文本 → unified diff markdown;相同文本 → diff_same 文案;lang 生效
- [ ] history 端点:默认 n=20,空日志返回空列表(PROMPT_LAB_LOG/PROMPT_LAB_PATH env 控制)
- [ ] TestClient 测试覆盖上述路径 + run/profiles 回归
- [ ] ruff/mypy/定向 pytest 通过
