# 项目协作规范

## 1. Git 提交规范

- 每次代码修改完成后,都必须跑 CLI 工具验证,验证不过先修复;然后立即提交 Git Commit，不允许泄露带有电子邮件和api key的文件。
- 提交信息清晰,例如 `feat: ...`、`fix: ...`。
- 不允许留下未提交的修改。
- 不添加 AI 的署名或 Co-authored-by 信息。

## 2. UI 设计规范

- 禁止使用蓝紫色及相关渐变。
- 保持整体视觉风格一致。
- 在可以用图形和按钮说明操作的情况下，不要添加多余的解释性文字
- 迁移/退役 Gradio 页到 React 前,先读 `docs/react_migration.md`(触点清单与先例)。

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

## 7. 批次工作流(修改类任务必须走此流程)

1. **只读调查**:阅读代码、复现问题,此阶段不修改任何文件。
2. **输出问题清单与批次划分**:按依赖关系、风险、修改范围分批;每个问题附证据(文件:行号/命令输出)。
3. **等待批准**:用户以"批次 N"等明确字样批准后才能动手;未批准的批次不得执行任何修改。
4. **只做已批准范围**:发现重大新问题或需扩大范围时,立即暂停并报告,等用户决定;失败后最多自主修复 3 次。
5. **验证**:按第 8 节命令执行(UI 改动加跑 uitest),并核对实际 git diff 与批准范围一致。
6. **结果报告落盘**:按 `docs/reports/TEMPLATE.md` 写入 `docs/reports/<YYYYMMDD>-<批次名>.md` 并随批次提交;同时在对话中交付。**未落盘报告 = 批次未完成**。
7. **遗留问题清单**(报告内必含):每条给出 证据 / 原因 / 影响 / 优先级(高中低) / 建议处理方式;没有则写"无"。
8. **等待用户圈选**下一步要处理的问题,再回到第 3 步。

**证据与诚实要求**:
- 未执行的步骤必须标记"未执行",不得假装完成;未运行的测试不得报告为通过。
- "验证已跑"的证据 = 报告中贴命令及其结尾输出行(如 `2902 passed`);"真浏览器已验"的证据 = 截图或报告路径;"已获批准"的证据 = 引用用户批准原话。
- 每批结束必须跑 `python scripts/check_workflow.py` 并在报告中附其输出(机械核对:无 AI 署名、工作区干净、报告已落盘)。

## 8. 本地验证命令

- `ruff check src tests`
- `mypy`(按 pyproject.toml `[tool.mypy]` files 白名单检查)
- `pytest`(默认跳过 uitest,见 pyproject 的 `addopts = "-v -m 'not uitest'"`)
- UI 相关改动:`python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm`
- 前端(frontend/)改动:`npm run lint --workspace <name>` + `npm run build --workspace <name>`(在 frontend/ 下执行)。
- 纯文档改动(docs/、*.md):至少跑 `ruff check src tests` + `pytest --collect-only -q` 确认仓库未损坏;不要求全量 pytest/uitest。
- 批次收尾:`python scripts/check_workflow.py`(工作流机械核对,FAIL 则本批次不得标记完成)。