# 批次结果报告:<批次名>(<YYYY-MM-DD>)

## 批准依据

> 引用用户批准本批次的原话,例如:"批次 1 开始"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高/中/低 | 改了什么 | 路径 | hash |

## 验证结果

逐条贴命令与结尾输出行(未运行的命令不得出现在此节):

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in N source files
pytest -q              -> N passed, M skipped
python scripts/check_workflow.py -> <输出>
```

UI 改动附 uitest 结果与截图/报告路径。

## 前后差异

- 测试类:前后测试结果对比(数字)。
- UI 类:截图路径对比。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 高/中/低 | … | 文件:行号 / 命令输出 | … | … | … |

没有则写"无"。

## 未执行的步骤

明确列出本批次跳过/未执行的步骤及理由;没有则写"无"。
