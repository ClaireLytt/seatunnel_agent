# 批次结果报告:架构深化 D1 前端骨架四件套 + D2 安全清理工具(2026-10-22)

## 批准依据

> 用户经第二轮架构评审后依次 `/to-spec`、`/to-tickets`、`/implement-spec`(spec:.scratch/arch-deepen-3/spec.md,D1+D2 双 Strong 候选);分支假设 dev 直提(spec 内声明,未被否决)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票01 D2:scripts/cleanup_worktrees.py(resolve 全前缀白名单/逐个 remove/失败即非零/零删除回退/默认 dry-run)+6 单测(含事故场景与静态禁 token 守卫);CLAUDE.md §9 加唯一入口条款 | scripts/、tests/test_cleanup_worktrees.py、CLAUDE.md | 票01 commit |
| 高 | 票02 D1 expand:@shared 四件套(PageHeader/useRunner/initI18n/fetchJson)+btnPrimary/btnGhost/langOf;试点 doc_qa+issue_triage(362→280 行) | frontend/shared/、两试点 | 票02 commit |
| 高 | PageHeader 补 titlePrefix(emoji 承载,解锁 emoji header 统一) | shared/PageHeader.tsx | 独立 commit |
| 高 | 票03 migrate A:8 页(+113/−332;流式页/仪表盘不硬塞 useRunner,如实记录) | 8 workspace src | 票03 commit |
| 高 | 票04 migrate B:8 页(+84/−356;emoji 经 titlePrefix 归一,漂移修复 mb-3→mb-4/text-3xl→text-4xl/mt-2→mt-3;结构化 detail 端点不换 fetchJson) | 8 workspace src | 票04 commit |
| 高 | 票05 migrate C:7 页(+38/−192)+ 主会话补 code_fix/web_task header(titlePrefix 就绪后);13 个 i18n 对账测试跟进新缝(叶子断言 initI18n,cookie 行为断言收敛至 shared) | 7 workspace src、tests/test_*_i18n.py ×13 | 本报告同批提交 |

**收尾核对**:25/25 i18n.ts 走 initI18n(grep 空);PageHeader 覆盖 23/25(seatunnel/text2sql header 结构不同构——text-2xl/边栏内/无 home 链接,正当保留)。**更正记录(2026-10-22 复核)**:本报告首版写 23/25 时实际为 22/25——sql_fmt 在票 03 因 emoji 跳过后、titlePrefix 落地时仅补了 code_fix/web_task 而漏掉;prove-it-works 复核(grep 逐页核对)发现后已补切(`fix` commit),现 23/25 为真值,核查命令:`grep -rln "<PageHeader" frontend/*/src/App.tsx | wc -l`;fetchJson 覆盖全部非结构化 detail 的 REST(结构化 {code,path} 端点如实保留,sql_fmt 先例);useRunner 落在贴合的单请求页(llm_eval/prompt_lab/doc_qa/issue_triage 等),流式/多面板页不硬塞。

## 验证结果

```
25 workspace npm lint+build -> 全绿(各票逐页跑)
各票定向页测 -> 票02: 8 passed · 票03: 48 passed · 票04: 94 passed · 票05: 60 passed(t2s 4 例为本机无 API_KEY 的既有环境失败,git stash 对照 HEAD 同样失败)
ruff check src tests   -> All checks passed!(exit 0)
mypy                   -> Success: no issues found in 109 source files
pytest -q              -> 3292 passed, 1 skipped, 237 deselected
  (首跑 13 failed:i18n 对账测试断言叶子含 lng: langFromCookie(),该行为已进共享 initI18n;
   测试跟进新缝后全绿——行为未变,断言位置变)
uitest smoke --no-llm  -> PASS 22 · FAIL 0(runs/20261022_074814/report.html)
python scripts/check_workflow.py -> 随本批次收尾执行,输出附对话
```

## 前后差异

- 行数:25 页骨架净删 ~870 行(试点 −82、A −219、B −272、C −154+补切 ~−34),共享实现 ~170 行一处;cleanup 工具 +~90 行(新能力)。
- 局部性:header 样式/错误归一/i18n init/HTTP 错误解析各收敛到一处;两处历史漂移 header 恢复一致;事故规则从文档变为可执行+可单测代码。
- 杠杆:ci_inspect 第 26 个 workspace 可零样板起步。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | seatunnel/text2sql header 未统一(结构不同构) | 票05 汇报 | 真差异非重复 | PageHeader 覆盖 23/25 | 保持;若要统一需设计扩展另议 |
| 低 | test_t2s_page 4 例本机无 API_KEY 失败(HEAD 同样失败) | 票05 对照实验 | 环境 | 本机全量 uitest 红 | 配置 .env 或 fixture 内 skip,另票 |
| 低 | 各页按钮串与共享 btnPrimary 存在 px-4/px-6 等微差未强改 | 票04 核对 | 改了即视觉变化 | 无 | 如需统一属视觉改版,另议 |
| 低 | PostToolUse 钩子引用的 tools/ui_check_hook.py 不存在,每次写文件报 Errno 2 | 本会话多次 | settings.json 配置超前于脚本 | 噪音 | 用户补脚本或移除钩子配置 |

## 未执行的步骤

无(推送:T1 已推;T2–T5 随本批收尾推送,若网络/代理再断则下个窗口补推并在对话中说明)。
