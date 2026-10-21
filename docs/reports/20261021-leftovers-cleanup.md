# 批次结果报告:遗留清零(换色/警告/chunk/截图输出,2026-10-21)

## 批准依据

> 用户以 `/to-spec 给其他问题解决` 圈选全部剩余遗留项,随后 `/to-tickets`、`/implement-spec` 启动(spec:.scratch/leftovers-cleanup/spec.md,含"我选合规色、用户过目可一票否决"约定);分支沿用 plat 直提。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | 票01:紫卡换色——orchestrator #7c3aed→#b91c1c(深砖红)、issue_triage #9333ea→#14b8a6(青绿);附 25 卡现值去重表;hub /ai 截图 docs/reports/shots/hub-ai-recolor.png 供过目 | 两 manifest | 74840f1 |
| 低 | 票02:data_skew react-refresh 警告清零(ConnHandoff/readConnHandoff 抽到独立文件) | frontend/data_skew/src/ | a96a822 |
| 中 | 票03:shared vite 基座 manualChunks(vendor-react/vendor-charts 函数式拆分);25 build 全绿,23 个零警告 | frontend/shared/vite.base.ts | c59372a |
| 中 | 票04:页测截图输出 docs/reports/shots→runs/shots(gitignore 覆盖);9 个页测 SHOTS 常量改指;react_migration.md 写入约定(正式对比图人工复制入 docs) | tests/test_*_page.py ×9、docs/react_migration.md | 本报告同批提交 |

## 验证结果

```
npm run lint --workspace data_skew -> 0 errors 0 warnings;25 workspace lint 保持全绿
25 × npm run build -> 全部 exit 0;chunk >500kB 警告 23 个清零
抽样页测(llmeval/llmcost/t2s)-> 30 passed;dataskew -> 20 passed
票04 验收:seatunnel+docqa 页测 9 passed 后 git status 的 docs/ 不再出现 PNG 改动,截图落 runs/shots/
ruff check src tests   -> All checks passed!(exit 0)
mypy                   -> Success: no issues found in 109 source files
pytest -q              -> 3286 passed, 1 skipped, 237 deselected
uitest smoke --no-llm  -> PASS 22 · FAIL 0(runs/20261021_105256/report.html)
python scripts/check_workflow.py -> 随本批次收尾执行,输出附对话
```

## 前后差异

- 颜色:AI workspace 两张违规紫卡清零(截图 hub-ai-recolor.png,待用户过目,可一票否决重选)。
- lint:data_skew 1 warning→0,全仓 25 workspace lint 0 错 0 警告。
- 构建:chunk 警告 6+ 处→2 处(mermaid 懒加载 chunk,按需加载非首屏,如实保留);首屏主 chunk 普遍下降(如 change_impact index ~340KB)。
- 工作区卫生:跑任何页测不再弄脏 git 工作区。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | **新发现**:data/devops workspace 还有 6 张卡在蓝紫区(data_comparison #8b5cf6、log_inspect #7c3aed、metric_diff #9333ea、sql_fmt #4f46e5、mcp_toolbox #6366f1、schema_drift/ci_inspect #2563eb) | 票01 的 25 卡色值表 | 本批只批准 AI 两张,发现即报告未扩大范围 | 规范违反面比已知更大 | 等用户圈选是否统一换色 |
| 低 | change_impact/data_lineage 的 mermaid 懒加载 chunk 警告(1.45MB/544KB) | 票03 记录 | elkjs/cytoscape 体积,按需加载 | 非首屏,无感 | 接受现状或升级 mermaid 另议 |

## 未执行的步骤

无。
