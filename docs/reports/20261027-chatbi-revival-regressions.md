# 批次结果报告:复活路径回归测试(2026-10-27)

## 批准依据

> 用户对第十轮候选(建议"1(回归测试)马上做")回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | REST run-now 端到端:TestClient 创建 sqlite 订阅 → run → 断言 status=success 且 last_status 落盘(此前该端点把 SubscriptionStore 当 schema_store,从未成功) | tests/test_t2s_subscriptions_api.py | 本批 |
| 高 | 连接预设解析:临时 ConnectionPresetsStore 存 sqlite 预设 → resolve_db_config 命中与未命中(此前 import 不存在的 PresetsStore,必炸) | tests/test_text2sql_subscriptions.py | 本批 |
| 高 | CJK 字体 PDF:monkeypatch 字体路径为本机任一 TTF/OTF 真走 add_font 注册路径(fpdf 2.8.8 无 uni 参数,旧代码必 TypeError);无字体机器跳过 | tests/test_text2sql.py | 本批 |

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 172 source files
三条定向测试               -> 3 passed（run_now/preset 2 passed + cjk pdf 1 passed）
python -m pytest -q          -> 3454 passed, 1 skipped, 243 deselected in 155.75s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3451 → 3454 passed(+3)。三条上批修活的路径现在有锁,复发即红。
- 无生产代码改动。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | CJK PDF 测试在无任何 TTF/OTF 的机器(极少)会 skip | 本批测试 | 真字体无法凭空生成 | CI 若无字体则该路径不验 | CI 镜像带 DejaVu,已覆盖常见情况 |

## 未执行的步骤

- uitest smoke:未执行(纯测试改动)。
- 其余无。
