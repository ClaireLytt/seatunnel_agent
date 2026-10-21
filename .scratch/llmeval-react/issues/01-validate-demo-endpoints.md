# 01: 后端薄端点 validate + demo(+ API 测试)

**What to build:** 客户端 POST 套件 YAML 可得到"解析 ok / 本地化错误信息"(只解析不跑、不调 LLM);GET 可取示例套件文本(内容含 text2sql-golden)。run/history/health 行为不变;suite/runner/scoring 引擎零改动。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] validate 端点:合法套件 → ok+用例数;非法(如 `cases: 42`)→ 本地化错误(含"期望顶层");空文本 → 本地化"请先粘贴"类提示(400 或 ok=false,沿 Gradio 文案)
- [ ] demo 端点:返回示例套件文本,含 "text2sql-golden"
- [ ] TestClient 测试覆盖上述路径 + run/history 回归不动
- [ ] ruff/mypy/定向 pytest 通过
