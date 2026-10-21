# 01: D2 — scripts/cleanup_worktrees.py(TDD)

**What to build:** 唯一的 worktree 清理入口:枚举 `git worktree list --porcelain`;每条路径 resolve 后必须以 `<repo>/.claude/worktrees/agent-` 为完整前缀(禁子串匹配),否则列为跳过;逐个 `git worktree remove <path>`(先不 --force),任一失败收集后整体退出非零并打印未删清单,**绝无 rm/Remove-Item/静默回退**;默认 dry-run 打印完整目标清单,`--yes` 才执行;全部成功后才 `git worktree prune`。单测(临时 git 仓库夹具,先例 tests/test_code_fix.py make_project):主仓库路径含 "agent" 不入选、前缀外拒绝、dry-run 不删、remove 失败→非零且无回退、--yes 正常删。CLAUDE.md §9 末尾加一行指向该脚本。

**Blocked by:** None

**Status:** ready-for-agent

- [ ] 五个单测场景绿;ruff/mypy 绿
- [ ] 脚本零删除回退路径(代码审读确认)
- [ ] CLAUDE.md §9 指向语句已加
