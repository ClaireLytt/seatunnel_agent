# 项目协作规范

## 1. Git 提交规范

- 每次代码修改完成后,都必须跑 CLI 工具验证,验证不过先修复;然后立即提交 Git Commit。
- 提交信息清晰,例如 `feat: ...`、`fix: ...`。
- 不允许留下未提交的修改。
- 不添加 AI 的署名或 Co-authored-by 信息。

## 2. UI 设计规范

- 禁止使用紫色、蓝紫色及相关渐变。
- 保持整体视觉风格一致。

## 3. 工作原则

- **先思考,再编码**:不要擅自假设需求;遇到歧义先说明假设、分析方案,必要时向用户确认。
- **保持简单**:只实现用户要求的功能,不添加多余功能、抽象或复杂设计。
- **精准修改**:只修改与需求直接相关的代码,不顺手重构其他模块;只清理自己此次修改产生的无用代码。
- **以结果为导向**:先明确成功标准和执行计划,再通过测试、构建等方式验证结果,发现问题就继续修复。
- **优先复用现有代码**:对于确实需要重复使用的逻辑,抽象为可复用函数,避免重复造轮子。


## 4. Evidence-First Problem Solving
Before asking the user a question, first investigate whether the answer can be derived from available evidence.
1. Inspect before asking. Read relevant source files, configuration, tests, documentation, logs, Git history, and available tool outputs.
2. Verify assumptions. Reproduce the issue or run targeted tests when feasible. Do not treat an untested hypothesis as a confirmed root cause.
3. Cite evidence. Support factual claims with file paths, line references, command output, test results, or other verifiable sources.
4. Separate facts from hypotheses. Clearly label confirmed facts, plausible explanations, and unknowns.
5. Never fabricate evidence. If evidence is unavailable or verification fails, state what is missing and what was attempted.
6. Ask only when necessary. Ask the user only when the decision depends on their intent, preferences, authorization, or information that cannot reasonably be obtained from available sources.
7. Minimize interruptions. When safe, proceed with a reversible, evidence-supported default. State the assumption and verify the result.
8. Verify completion. After making changes, run the relevant checks and report actual results. Never claim a check passed unless it was executed successfully.
9. Failure attribution (three steps):
   - step1: After a failure, first read CLAUDE.md and docs/pitfalls.md for prior evidence and lessons.
   - step2: Every conclusion must carry evidence (file path / command output / test result).
   - step3: When evidence is insufficient, design a minimal experiment yourself (minimal repro script, extra logging, bisection) to locate the cause before concluding.

## 5. 验证闭环

- 每次修改必须走闭环:分析 → 解决 → 验证 → 未通过则再次分析修复 → 通过后反馈前后差异。
- 差异反馈形式:
  - 测试类改动:给出测试结果的前后对比。
  - UI 类改动:给出截图/可视化对比(可用 `seatunnel-agent uitest` 产出的截图)。

## 6. 重复犯错记录

- 同类错误出现 ≥2 次时,必须把问题、根因、规避方法追加到 `docs/pitfalls.md`,供人类查阅。
- 动手前先查 `docs/pitfalls.md`,避免重蹈覆辙。

## 7. 阶段二:自主任务流程

1. 明确需求。
2. 解释计划。
3. 修改代码。
4. 自动验证:ruff / mypy / pytest;UI 改动加跑 uitest。
5. 失败后最多自主修复 3 次。
6. 输出结果报告(**每次代码修改验证完成后必须立即交付,不得只给进度汇报**),固定格式:
   - **已完成**:改了什么(文件 + commit hash)。
   - **验证结果**:跑了哪些验证命令、实际输出结论(测试数、PASS/FAIL)。
   - **前后差异**:测试结果对比或截图对比(见第 5 节)。
   - **未解决问题 / 取舍**:明确列出,没有则写"无"。

## 8. 本地验证命令

- `ruff check src tests`
- `mypy`(按 pyproject.toml `[tool.mypy]` files 白名单检查)
- `pytest`(默认跳过 uitest,见 pyproject 的 `addopts = "-v -m 'not uitest'"`)
- UI 相关改动:`python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm`
- 纯文档改动(docs/、*.md):至少跑 `ruff check src tests` + `pytest --collect-only -q` 确认仓库未损坏;不要求全量 pytest/uitest。