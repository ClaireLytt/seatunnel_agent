# 批次结果报告:ci-install-hardening(2026-10-28)

## 批准依据

> 用户:"go on"(对「CI 防卡死硬化」提案的批准;调查后范围修正:job 超时与 pip cache 已存在,实际缺口为步骤级超时与 pip 重试)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | ui-smoke / tests 的 Install dependencies 步骤加 `timeout-minutes: 6` + `PIP_DEFAULT_TIMEOUT=60`/`PIP_RETRIES=3`:卡死 6 分钟快速失败(原先吊满 20 分钟 job 预算),瞬时抖动 pip 自愈 | .github/workflows/uitest.yml, tests.yml | 本批次 |
| 高 | pitfalls 追加「CI ui-smoke 卡死 ≥2 次」条目(问题/根因/机械化规避/人工 cancel→rerun 口径) | docs/pitfalls.md | 本批次 |

## 验证结果

```
ruff check src tests scripts         -> All checks passed!
pytest --collect-only -q             -> 3517/3766 tests collected (249 deselected)
python -c "yaml.safe_load(每个 workflow)" -> workflows yaml ok
python scripts/check_workflow.py     -> 提交后全 [PASS](见对话)
```

CI/文档改动;真实防卡效果由下一个 PR 的 CI 运行验证(标注:未在本批执行)。

## 前后差异

- 行为:本会话两次 ui-smoke 卡死各耗 ~6-9 分钟人工干预;此后同类卡死 6 分钟自动失败可重跑,瞬时抖动由 pip 重试吸收。
- 文档:pitfalls 新增复发问题条目(满足第 6 节 ≥2 次必须记录的要求)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 步骤超时后仍需人工点重跑(GitHub 无原生自动 retry job) | workflows 无 retry 机制 | 平台能力限制 | 卡死时仍有一次人工动作 | 如频发再引入 re-run action |

## 未执行的步骤

- 全量 pytest / uitest:无 src/tests 代码改动;新 CI 配置的实际效果在下一个 PR 的 CI 中验证。
