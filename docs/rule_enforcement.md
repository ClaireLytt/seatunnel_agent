# 规则 ↔ 强制点对照表

重复犯错(≥2 次)的规则必须有机械强制点;新增规则时同步登记,靠本表发现"写了规则没人执行"的缺口。

| 规则 | 强制点 |
| --- | --- |
| heredoc 体内禁反斜杠/中文 | 全局 PreToolUse hook(~/.claude/hooks/block_heredoc.py,本机) |
| 控制台输出 UTF-8 | .claude/settings.json env `PYTHONUTF8=1`(本机,未入库);check_workflow.py 自身也 reconfigure stdout |
| commit 无 AI 署名 | scripts/check_workflow.py + CI workflow-check |
| 工作区干净 / 批次报告落盘 | 同上 |
| 批次报告必须粘贴 check_workflow 输出(§7) | scripts/check_workflow.py `报告含验证输出` 检查 + tests/test_check_workflow_floor.py |
| worktree 清理四规则 | scripts/cleanup_worktrees.py + tests/test_cleanup_worktrees.py |
| 前端目录名 = manifest.name | tests/test_registry.py::test_external_manifest_names_match_frontend_workspace_dirs |
| uitest 用例计数与 YAML 同步 | tests/test_ui_testing.py 派生断言(对账 YAML 源) |
| lint 范围含 scripts/ | CI lint.yml + 第 8 节命令 |
| 不泄露 api key/凭证(第 1 节) | CI lint.yml secretscan job + tests/test_secret_scan.py::test_repo_dogfood_no_high_findings(豁免配置 .secretscan.yaml) |
| 目录入参先白名单后存在性(bad_dir) | common/api_guard.require_dir 单源 + 各 agent API 测试 |
| 禁作弊变绿(floor:新增压制注释、测试 skip/删断言/删文件、mypy 白名单缩水、桩子/TODO 顶实现) | scripts/check_workflow.py floor 检查 + tests/test_check_workflow_floor.py + CI workflow-check |
| UI 改动交用户验证后再提交 | 无机械强制(判断型,见 CLAUDE.md 第 5 节)——仅此类规则允许停留在文档层 |
