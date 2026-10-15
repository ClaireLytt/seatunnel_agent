# 批次结果报告:workflow-check 接入 CI(2026-10-15)

## 批准依据

> 用户:"脚本未接入 CI 解决这个问题"(遗留清单圈选)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 低 | check_workflow.py 新增 `--range` 参数(CI 中无"未推送"概念,需显式指定 PR 范围) | scripts/check_workflow.py | 本批次 |
| 低 | lint.yml 新增 workflow-check job(仅 PR 触发,fetch-depth 0,核对 `origin/<base>...HEAD`) | .github/workflows/lint.yml | 本批次 |
| 低 | 本报告(首份正式落盘报告,同时满足本 PR 的报告落盘门禁) | docs/reports/20261015-ci-workflow-check.md | 本批次 |

## 验证结果

```
python -c "yaml.safe_load(lint.yml)"              -> yaml ok
ruff check scripts/check_workflow.py src tests    -> All checks passed!
python scripts/check_workflow.py --range origin/main...HEAD
  -> [PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘(本文件)
远端 CI:见 PR #50 workflow-check job(推送后由 CI 实证)
```

## 前后差异

- 前:署名/报告落盘检查只在本地人工触发;后:每个 PR 由 CI 强制核对。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 报告落盘门禁对外部贡献者/机器人 PR 同样生效 | lint.yml workflow-check 无豁免条件 | 门禁按 PR 范围统一核对 | dependabot 改 pyproject 不触发(非 src/tests);但外部改 src 的 PR 会被要求带报告 | 若出现误拦,给 job 加 `github.actor != 'dependabot[bot]'` 类豁免 |

## 未执行的步骤

- 全量 pytest/uitest:本批改动为脚本参数 + CI 配置 + 文档,按第 8 节 docs-only 标准执行(ruff + collect + 脚本实跑)。
