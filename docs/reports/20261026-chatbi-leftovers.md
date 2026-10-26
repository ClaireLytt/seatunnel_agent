# 批次结果报告:chatbi 审计遗留三项(2026-10-26)

## 批准依据

> 用户对审计报告遗留清单(webhook 白名单 / 字体校验 / 无 AS 别名脱敏)回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 低 | webhook 域名白名单:`T2S_WEBHOOK_ALLOW_HOSTS` 后缀匹配,push_card 统一拦截,邮件渠道豁免;未设置保持开放 | notify.py | 本批 |
| 低 | 字体下载供应链:原 URL 文件名本就不存在(一直静默 404);改为 tag 固定地址 `Sans2.004/NotoSansCJKsc-Regular.otf` + 默认 sha256 校验(`T2S_FONT_SHA256` 可覆盖) | exporter.py | 本批 |
| 低 | 脱敏别名盲区:alias_kinds 改 sqlglot 投影解析优先(覆盖 `SELECT t.user_phone p` 无 AS 写法),解析失败回退原正则 | masking.py | 本批 |
| — | 指南安全提示补 `T2S_WEBHOOK_ALLOW_HOSTS` 用法 | docs/chat_bi_guide.md | 本批 |

新增测试 2 条(裸别名脱敏 / webhook 白名单),tests/test_text2sql_masking.py。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 107 source files
python -m pytest tests/test_text2sql_masking.py -q -> 12 passed in 4.30s
python -m pytest -q          -> 3409 passed, 1 skipped, 243 deselected in 152.50s
字体真实下载验证            -> downloaded 16,437,364 字节,sha256=2c76254f...365b74b(已固化为默认校验值)
python scripts/check_workflow.py(提交后终检输出):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3407 → 3409 passed(+2)。
- 行为:设 `T2S_WEBHOOK_ALLOW_HOSTS` 后非白名单 host 推送直接拒绝并给原因;PDF 导出中文字体从"永远下载失败"变为可用且带校验;`SELECT t.user_phone p` 现在同样脱敏。
- 非 UI 改动,uitest 未执行。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
