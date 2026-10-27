# 批次结果报告:skew-readme(2026-10-28)

## 批准依据

> 用户:"go on"(对「README 数据倾斜章节补齐七个 PR 能力」提案的批准)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | README 英文/中文「数据倾斜」节重写:补 splitkey 体检(--apply/目录巡检/webhook/sink 键)、skew-drift(基线/热点值/去重告警/--fail)、skew-runtime(eventlog/History Server/--flink/复测/桥接)三大块;CLI 示例块补 6 条代表命令;链接 docs/data_skew_guide.md | README.md | 本批次 |

## 验证结果

```
ruff check src tests                 -> All checks passed!
pytest --collect-only -q             -> 3516/3765 tests collected (249 deselected)
python scripts/check_workflow.py     -> 提交后全 [PASS](见对话)
```

纯文档改动,按第 8 节仅要求以上两项;未跑全量 pytest/uitest。

## 前后差异

- 文档:README 两个语言节此前停留在"静态规则 + LLM 改写 + 实测探查"(CLI 仅 skew/skew-stats/skew-mcp);现在与七个已合并 PR 的能力一致。

## 未解决问题 / 遗留清单

无。

## 未执行的步骤

- 全量 pytest / uitest:纯文档改动,第 8 节不要求。
