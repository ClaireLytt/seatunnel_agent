# 01: 薄端点 /prices(+ API 测试)

**What to build:** 客户端 GET 可取合并后价目表(prefix/input_usd/output_usd/source,override 优先)与 override 文件路径信息;内置价目含 deepseek-chat。summary/health 行为不变;aggregate/pricing 引擎零改动。

**Blocked by:** None (can start immediately)

**Status:** ready-for-agent

- [ ] prices 端点:返回价目列表 + override 路径;SEATUNNEL_PRICING_PATH override 生效
- [ ] malformed override 的错误传达与 summary 端点一致(400)
- [ ] TestClient 测试覆盖内置/override/malformed + summary 回归
- [ ] ruff/mypy/定向 pytest 通过
