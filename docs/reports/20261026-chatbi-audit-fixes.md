# 批次结果报告:chatbi 安全审计修复(批次 1–3)(2026-10-26)

## 批准依据

> 用户在审计问题清单与"建议批次 1/2/3"之后回复:"go on"(理解为按序执行全部三个批次)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 批1:逗号 JOIN 表白名单绕过——extract_tables 改为 sqlglot AST 优先(覆盖逗号连接/子查询/UNION),解析失败回退逗号感知正则 | src/seatunnel_agent/agents/data/text2sql/validator.py | 07869aa |
| 中 | 批2:enforce_limit 对尾注释 SQL 不再追加第二个 LIMIT(字面量感知的尾注释剥离,超限 LIMIT 在注释下也能封顶) | src/seatunnel_agent/agents/data/text2sql/validator.py | 07869aa |
| 中 | 批3:脱敏别名绕过——apply_masking 可选 sql 参数,`敏感列 AS 别名` 的别名继承脱敏;execute_sql 预览/三种导出/看板/订阅卡片全部传入 SQL | masking.py, tools_sql.py, tools.py, boards.py, notify.py, subscriptions.py | 见下一提交 |
| 低 | 批3:文档安全提示——未设 SEATUNNEL_API_KEY 时 API 全开、订阅 webhook 任意 URL(SSRF 面) | docs/chat_bi_guide.md | 见下一提交 |

回归测试:tests/test_text2sql.py 新增 TestValidatorCommaJoinWhitelist(5 条)+ TestEnforceLimit 4 条;tests/test_text2sql_masking.py 新增 3 条。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 107 source files
python -m pytest -q          -> 3403 passed, 1 skipped, 243 deselected, 2 warnings in 149.64s
python scripts/check_workflow.py -> (输出附在对话中,提交后执行)
```

绕过复现(修复前,真实命令输出):

```
validate_sql('SELECT * FROM allowed_t, secret_t', store)
-> ok=True, tables=['allowed_t']        # secret_t 漏检
enforce_limit('SELECT * FROM allowed_t LIMIT 5 -- tail comment')
-> '...LIMIT 5 -- tail comment\nLIMIT 1000'   # 双 LIMIT 非法 SQL
apply_masking(['p'], [('13812345678',)])  # SELECT user_phone AS p
-> 原值外泄
```

修复后三者分别:拒绝(whitelist 报错)/ 保持原 SQL / `138****78`。

## 前后差异

- 测试:3396 passed → 3403 passed(+12 新增回归,其中 5 条在修复前会失败)。
- 非 UI 改动,无截图;uitest 未执行(未触碰前端/页面)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 订阅 webhook 仍可指向任意 URL(仅文档提示,无域名白名单) | api_subscriptions.py:32 | 多渠道按 URL 识别,白名单需配置面 | 内网部署+未设 API key 时可被用作 SSRF 跳板 | 如需硬约束,加 `T2S_WEBHOOK_ALLOW_HOSTS` 环境变量白名单 |
| 低 | exporter 字体从 GitHub 裸下载无校验和 | exporter.py:17 | 便利性设计,失败安全降级 | 供应链面极小(仅 PDF 字体) | 固定 release URL + sha256 校验 |
| 低 | 脱敏别名检测基于正则,`SELECT t.user_phone p`(无 AS)不覆盖 | masking.py alias_kinds | 保持零依赖轻实现 | LLM 生成 SQL 几乎总用 AS,残余面小 | 如需全覆盖改 sqlglot 投影解析 |

## 未执行的步骤

- uitest smoke:未执行(本批无 UI/前端改动)。
- 其余无。
