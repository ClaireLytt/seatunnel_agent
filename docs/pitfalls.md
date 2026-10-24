# 踩坑记录(pitfalls)

同类错误出现 ≥2 次时,必须在此追加一行:问题现象、根因、证据、规避方法。动手前先查本表。

| 日期 | 问题现象 | 根因 | 证据 | 规避方法 |
| --- | --- | --- | --- | --- |
| 2026-10-15 | Windows 下用 shell heredoc 写文件,中文字符损坏、反斜杠被剥离(即使加引号) | Windows shell 对 heredoc 的编码/转义处理与 POSIX 不一致 | 经验记录 | 写含中文或反斜杠的文件一律用编辑器/Write 工具,不用 heredoc;脚本 stdout 显式包成 UTF-8 |
| 2026-10-15 | Gradio 隐藏 textbox 在真实浏览器提交时值为 None,但 gradio_client 测试通过 | 真实浏览器不提交 hidden 组件的值,gradio_client 走的是 API 路径,绕过了前端行为 | 经验记录 | UI 行为类 bug 必须用 Playwright/真实浏览器(uitest smoke 套件)验证,不能只靠 gradio_client。两处疑似同型实例已于 2026-10-15 用真实浏览器逐一验证:(1) text2sql `/history` 行选择(`ui.py` `#hist-sel-idx`):功能正常,但走的是 `history_table.select` 原生事件路径(点击单元格 → "Selected row #0" + 详情 SQL 渲染,见 `runs/adhoc/t2s_hist/debug3_after_click.png`);隐藏 textbox + 行点击 JS 路径在 Gradio 6 下是**死代码**——`visible=False` 的 Textbox 根本不挂载 DOM(`querySelector('#hist-sel-idx …')` 为 null),且 Dataframe 可见网格已不是 `table tbody tr`,JS 只绑到隐藏的测量行上,写值是静默 no-op,不触发也不致错(行高亮 `.st-row-selected` 因此从不生效,但 Gradio 自带单元格选中高亮兜底)。(2) data_comparison 查看报告(`ui.py` `dc-hidden-report`):功能正常,pitfall 不适用——数据流是后端 output → 前端组件 store → `.then(js=...)` 读 store 值新开标签页,不依赖浏览器"提交" hidden 组件;adhoc 实测弹出页含完整报告("数据比对报告/行数 10 vs 9",见 `runs/adhoc/dc_view_report/`)。结论:该坑只命中"前端 JS 改 DOM 值→期望后端收到"的方向;后端→前端 js 读值方向安全;Gradio 6 下 hidden 组件甚至不在 DOM 中,JS 直改 DOM 的 workaround 整体失效,传值一律用 cookie + `gr.Request` 或可见组件 |
| 2026-10-15 | Gradio 6 中 `js=` 返回值不会替换 fn 的 inputs;Dropdown choices 在 build 时固化;DownloadButton 对路径有 cwd/temp 限制 | Gradio 6 前后端数据流约定所致 | 经验记录 | 需要把前端值传给后端时用 cookie + `gr.Request`;动态选项用事件回调更新;下载文件放在 cwd 或系统临时目录 |
| 2026-10-15 | AI 代理提交 commit 时误加 `Co-Authored-By: Claude ...` 署名,同日发生 2 次(validator 修复、ruff 规则 commit),均事后 amend 移除 | 代理运行环境默认附加 AI 署名,与本项目 CLAUDE.md 第 1 节"不添加 AI 署名"冲突,代理首次提交时未复核 | 2026-10-15 两个子任务汇报中的 amend 记录(最终 hash 0793415、2f23203 均已无署名) | 每次 commit 前在提交信息中显式不含署名行;提交后用 `git log -1 --format=%B` 复核;发现即 amend |
| 2026-10-17 | Windows 控制台跑 `python -c`/脚本打印中文或 emoji 时 `UnicodeEncodeError (cp1252)`,同日 3 次(i18n 核对、check_workflow 输出等) | 控制台默认编码 cp1252,Python stdout 未包 UTF-8 | 2026-10-17 会话:check_workflow.py 首跑 Traceback,`-X utf8` 重跑即过 | 统一加 `-X utf8` 或设 `PYTHONUTF8=1`(已写入 .claude/settings.json env);脚本内也可显式包 stdout |
| 2026-10-17 | `config/t2s_examples.json` 在跑 uitest smoke/起 hub 后被改写(id/created_at 再生),同日 3 次弄脏工作区,其中 1 次混入无关 commit(9125b51,已还原) | text2sql 示例库默认落在仓库内 `config/t2s_examples.json`(examples.py:29 `T2S_EXAMPLES_PATH`),运行期写回 | 2026-10-17 三次 `git status` 出现 M config/t2s_examples.json | 提交前 `git status` 核对,发现该文件 M 且非本意改动一律 `git checkout --` 还原;根治待办:uitest/测试运行设 `T2S_EXAMPLES_PATH` 指向临时目录 |
| 2026-10-18 | 全量 pytest 跑完后 `config/t2s_examples.json` 被改写(示例 id/created_at 再生成),漂移已两次混入提交(9125b51 及 66e0048 所还原的那次),与 2026-10-17 行同根因、场景扩大到全量 pytest | text2sql 示例库默认路径指向仓库内 `config/t2s_examples.json`(examples.py `T2S_EXAMPLES_PATH`),测试/运行期写回文件,id 与时间戳每次再生 | 本批次全量 pytest 后 `git status` 再现 `M config/t2s_examples.json`;历史提交 9125b51(已还原)、66e0048(revert commit) | 提交前必查 `git status`,该文件非本意改动一律 `git checkout -- config/t2s_examples.json`;根治建议:给测试加 fixture 把 `T2S_EXAMPLES_PATH` 重定向到 tmp_path(测试隔离),或将示例库移出 git 跟踪 |
| 2026-10-18 | React 页静态挂载落空:/datacompare 一直显示"frontend is not built"提示页,即使 dist 已构建;同类"构建/挂载约定靠字符串对齐"问题已出现 2 次(stale dist + 目录名错位) | hub 按 `frontend/<manifest.name>/dist` 挂载(registry.frontend_dist),票 02 把 workspace 目录建成了路由名 `datacompare` 而 manifest 名是 `data_comparison`;页面 Playwright 测试自行 mount dist,绕过了该约定,所以全绿漏检 | commit 615482a(重命名修复);hub 提示页文案引用 manifest 名 | 新建 workspace 时目录名必须等于 manifest.name(react_migration.md 已加检查项);页面测试取 dist 路径应走 `registry.frontend_dist()` 而非自拼路径;前端改动后用 `seatunnel-agent ui --build` 一步构建+启动 |
| 2026-10-15 | pip-audit 硬门禁被 CI runner 环境自带工具的漏洞误触发,同日 2 次:先是 pip 26.0.1(本地预判),后是 setuptools 79.0.1(PYSEC-2026-3447,PR #50 CI 实际变红);两者都不是项目依赖 | pip-audit 审计整个环境,runner 预装的 pip/setuptools 版本滞后带已知 advisory | CI run 38756203384 日志:`setuptools 79.0.1 PYSEC-2026-3447 Fix 83.0.0`,ruff/mypy 同 run 均绿 | 审计前先 `python -m pip install --upgrade pip setuptools`;以后 runner 环境工具再误红,优先升级该工具而不是放宽门禁 |
| 2026-10-15 | 子代理只给进度汇报,未按阶段二第 6 步交付固定格式的结果报告 | 结果报告的格式和"每次修改后必须交付"当时未写入 CLAUDE.md,仅存在于口头需求 | 2026-10-15 批次 1-3 的汇报形式 | 已将结果报告固定格式(已完成/验证结果/前后差异/未解决问题)写入 CLAUDE.md 第 7 节;每次代码修改验证完成后必须立即交付 |
| 2026-10-17 | UI 改动后直接提交,未启动 app 让用户验证;跨多个 batch 连续犯 | 追求批次效率,跳过了 /implement skill 和 CLAUDE.md §5 要求的 UI 验证步骤 | 用户反馈:"做完一个功能就打开ui让我验证为什么还是做不到" | 每个 ticket 有 UI 改动时,implement 结束前必须: (1) 构建前端 (2) 启动 app (3) 给用户 URL (4) 等用户确认后才提交。不允许跳过。 |
| 2026-10-24 | 测试在仓库根写出运行产物(configs/demo_fake_to_console.conf),被 `git add -A` 一并提交,靠肉眼在 commit 输出发现才回滚;同根因本会话出现 3 处(两个旧 demo 测试 + 新测试初版都没 chdir) | 被测代码把"写文件到 cwd"作为行为,测试未隔离工作目录;check_workflow 只查"工作区干净",查不到**已被提交**的污染 | ticket-01 commit 输出中的 `create mode 100644 configs/demo_fake_to_console.conf`(随后 `git rm --cached` 回滚) | 凡被测代码会写 cwd,测试必须 `monkeypatch.chdir(tmp_path)`;机械强制点:tests/conftest.py 的 session 级 `_no_repo_pollution` fixture(测试会话前后对比 untracked,新增即 fail);提交尽量列明文件,少用 `git add -A` |
| 2026-10-24 | 环境依赖测试单跑红、全量绿:test_saved_sessions_list_and_resume 在无 API_KEY 的机器上单独跑必红,全量跑吃了别的测试留下的 env 而绿 | 测试经 connect→build_agent→load_settings 读真实环境 API_KEY,未自给自足,靠执行顺序掩盖 | 本会话 `pytest tests/test_t2s_history_api.py::test_saved_sessions_list_and_resume` 单跑 RuntimeError: API_KEY is not set,全量 3360 passed | 读环境配置的测试一律 `monkeypatch.setenv` 自给自足;单测失败先单跑复现,再跑全量对照,判别顺序依赖 |

## 后台 hub 任务"无故"退出(exit 1/127)
- **问题**:后台起的 `python -m seatunnel_agent.hub.ui` 任务在数十分钟后报 failed,日志为空,看似崩溃。会话内已出现 ≥3 次误判。
- **根因**:带 `SEATUNNEL_UI_KILL_PORT=1` 起新实例时会杀掉占用 7860 的旧实例 —— 被杀的就是上一个后台任务,其退出被任务系统报告为 failed。
- **规避**:起新 hub 前先显式停掉旧后台任务(TaskStop);或看到此类 failed 通知时,先确认是否刚启动过新实例,再按故障排查。

## 2026-10-22 worktree 清理删库事故(CLAUDE.md 第 9 节规则的出处)

批次收尾清理 worktree 时,AI 运行了:

```bash
git worktree list --porcelain | grep worktree | grep agent | sed 's/worktree //' \
  | while read w; do git worktree remove "$w" --force 2>/dev/null \
      || { rm -rf "$w"; git worktree prune; }; done
```

主仓库路径 `D:/ospp/seatunnel_agent` 本身含 "agent" 子串,被 `grep agent` 匹配进删除列表;`git worktree remove` 对主仓库的拒绝报错被 `2>/dev/null` 吞掉,`||` 回退执行了 `rm -rf 主仓库`,删掉了工作树与 `.git`,未推送分支(约 20 个提交、4 个批次成果)永久丢失。

三个独立失误叠加才酿成事故:子串匹配把主仓库卷入目标清单;静默守卫吞掉了最后一道拒绝;回退路径用了比原命令更强的删除手段。由此固化的规则见 CLAUDE.md 第 9 节,并已代码化进 `scripts/cleanup_worktrees.py`(单测 tests/test_cleanup_worktrees.py)。
