# /retro — 环境改进落地（脚手架/噪音/gate 文案/配方落盘）

日期: 2026-10-31 分支: fresh

## 候选与处置（按严重度）

1. **脚手架缺失**（本会话每个新 agent ~15 次重复手工调用 × ~15 个 agent）→
   `scripts/new_agent.py <name> --route /x --page-title "T"`：从捐赠 agent
   复制前端 workspace 并改路由/标题/API 前缀、注册 frontend/package.json、
   生成 standard_page_tests 的 spec（TODO 待填位）,末尾打印后端/CLI/守卫
   检查清单。不触碰未写的后端,脚手架后仓库保持绿。纯函数 + tmp_path 假仓
   测试 4 项（名称移植/注册位次/spec 内容/撞车拒绝）。
2. **CRLF 警告噪音**（每次提交 ~20 行 × 30+ 次提交）→ `.gitattributes`
   `* text=auto eol=lf` + 二进制例外;本次 staging 已验证警告消失
   （仅剩 check_workflow.py 自身 CRLF→LF 的一次性归一提示）。
3. **报告-gate 两步舞**（agent 66 曾因自拟标签 FAIL 多花一个修正提交）→
   check_workflow.py 的报错信息明说"把本次运行打印的全部 [PASS]/[FAIL]
   行原样粘进报告（自拟标签不算）"。
4. **配方无落盘导航** → `docs/agent_factory.md`（骨架表/复用链/台账三件套/
   PINS 守卫/收尾命令）,CLAUDE.md 规则表加指针行（CLAUDE.md 为本地文件,
   不入库）。
5. 未证实声明审计:全场声明均有运行输出背书;两处降级处理已在对应报告
   如实标注,无需改动。

## 验证

```
tests/test_new_agent_scaffold.py + test_collision_guards.py
============================== 6 passed in 3.21s ==============================
All checks passed!   (ruff)
git add -A → CRLF 警告由每次 ~20 行降为 1 行一次性归一提示
```

## Gate

```
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```
