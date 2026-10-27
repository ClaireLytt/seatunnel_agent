# 批次结果报告:ci-install-retry(2026-10-28)

## 批准依据

> 用户:"go on"(对「ui-smoke 安装步骤原地自动重试」提案的批准;触发条件:同故障第 4 次复发,上批遗留项"如频发再引入 retry"已满足)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | ui-smoke 安装步骤两段式原地重试:首次 `continue-on-error` + 6 分钟超时,失败触发同 run 第二次安装(缓存已热);无第三方 action | .github/workflows/uitest.yml | 本批次 |
| 中 | pitfalls 条目更新(第 4 次复发与新机制;人工口径降级为兜底) | docs/pitfalls.md | 本批次 |

仅动 ui-smoke(tests 从未卡过,不扩面)。

## 验证结果

```
python -c yaml.safe_load(uitest.yml)  -> yaml ok
ruff check src tests                  -> All checks passed!
pytest --collect-only -q              -> 3521/3770 tests collected (249 deselected)
python scripts/check_workflow.py      -> 提交后全 [PASS](见对话)
```

实效由携带本改动的 PR 的 CI 验证(标注:未在本批执行)。

## 前后差异

- 卡死处置链:人工盯+手动重跑(~9 分钟)→ #144 后 6 分钟自动失败+手动/看守重跑 → 本批后同 run 自动重试,零人工。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- 全量 pytest / uitest:纯 CI 配置改动,collect-only 验证仓库未损坏;实效在下一个 CI 运行中观察。
