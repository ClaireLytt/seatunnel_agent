# 批次结果报告:ci-nightly-retry(2026-10-28)

## 批准依据

> 用户:"go on"(对「uitest-nightly 同款安装硬化」提案的批准)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | nightly 两个 Install dependencies 步骤套用 #144/#149 已验证模式:6 分钟步骤超时 + pip 重试 env + 同 job 原地重试(夜跑 wedge 不再可能吊满 90 分钟且无人看) | .github/workflows/uitest-nightly.yml | 本批次 |
| 低 | pitfalls 条目文件清单补 nightly | docs/pitfalls.md | 本批次 |

## 验证结果

```
python -c yaml.safe_load(uitest-nightly.yml) -> yaml ok
ruff check src tests                         -> All checks passed!
pytest --collect-only -q                     -> 3521/3770 tests collected (249 deselected)
python scripts/check_workflow.py             -> 提交后全 [PASS](见对话)
```

nightly 为 schedule 触发,实效在下一次夜跑观察(标注:未在本批执行)。

## 前后差异

- nightly 安装卡死的最坏情形:90 分钟无人值守吊死 → 6 分钟自动失败 + 同 job 重试。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- 全量 pytest / uitest:纯 CI 配置改动;nightly 实跑待计划触发。
