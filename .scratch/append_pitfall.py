"""Move the 2026-10-22 worktree incident narrative from CLAUDE.md into
docs/pitfalls.md (retro fix 3)."""
from pathlib import Path

SECTION = '''
## 2026-10-22 worktree 清理删库事故(CLAUDE.md 第 9 节规则的出处)

批次收尾清理 worktree 时,AI 运行了:

```bash
git worktree list --porcelain | grep worktree | grep agent | sed 's/worktree //' \\
  | while read w; do git worktree remove "$w" --force 2>/dev/null \\
      || { rm -rf "$w"; git worktree prune; }; done
```

主仓库路径 `D:/ospp/seatunnel_agent` 本身含 "agent" 子串,被 `grep agent` 匹配进删除列表;`git worktree remove` 对主仓库的拒绝报错被 `2>/dev/null` 吞掉,`||` 回退执行了 `rm -rf 主仓库`,删掉了工作树与 `.git`,未推送分支(约 20 个提交、4 个批次成果)永久丢失。

三个独立失误叠加才酿成事故:子串匹配把主仓库卷入目标清单;静默守卫吞掉了最后一道拒绝;回退路径用了比原命令更强的删除手段。由此固化的规则见 CLAUDE.md 第 9 节,并已代码化进 `scripts/cleanup_worktrees.py`(单测 tests/test_cleanup_worktrees.py)。
'''

p = Path('docs/pitfalls.md')
t = p.read_text(encoding='utf-8')
assert '2026-10-22 worktree' not in t
p.write_text(t.rstrip() + '\n' + SECTION, encoding='utf-8')
print('pitfalls updated')
