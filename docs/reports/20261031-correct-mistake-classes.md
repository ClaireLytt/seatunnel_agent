# /correct — 重复错误类别的仓库级根治

日期: 2026-10-31 分支: fresh

## 错误类别、证据与处置层级

| 类 | 证据（≥2 次） | 处置层级与理由 |
|---|---|---|
| A. track_history 接线错 | kafkalag 时期字符串字段触发 ':g' 崩溃;今日 slaboard 漏 worse_key | **实现层拒绝坏状态**：入口校验数值-only 并点名违规字段,worse_key 必须在条目内。更高层（类型系统）在 dict[str, Any] 签名下无法表达,运行时命名校验是最高可行层 |
| B1. CLI 命令重名 | datadict 重名被迫改 dictgen（click 静默覆盖,靠两个无关测试才暴露） | **测试层**：test_collision_guards 全仓扫描 @click.command 名,点名撞车文件对。架构层（注册时抛错）需改 click 装配方式,收益不抵改动面 |
| B2. 新工具抢邻居路由 | ddl_evolve 关键词抢走 ddl_guard 署名问法（今日 test_ddl_guard 实际失败即历史实证） | **测试层单一事实源**：PINS 路由钉子表（7 条争议问法）,新 agent 领域相邻时必须补对方钉子;任何新工具合入都重跑全部钉子。架构层不可行——路由排序是全局行为 |
| C. 页面测试逐字复制 | 42 份同构 Playwright 文件 | **架构层已根治**：standard_page_tests 工厂,样板只有一份实现（上一轮完成,入表记录） |
| D. heredoc 中文/反斜杠损坏 | 两次损坏后建 hook | **已有强制**：PreToolUse block_heredoc.py 直接拦截（入表记录） |
| E. 生成类产出不可消费 | contract_gen 分区列洞、seatunnel_gen 引号键(两次靠回检守卫当场抓住) | **实现层惯例**：每个 generator 内置 round-trip guard,入表固化为规则 |

钉子表首跑即抓到 2 条归属含糊的问法（pin 本身不合格）,换成无争议署名问法后全绿——
测试的判别力得到现场验证。

## 实证（每项检查对真实历史错误失败）

```
A-proof: track_history entries must be numeric-only ... non-numeric key(s): group
A2-proof: worse_key 'misses' is not in the entry (keys: lag)
B2-proof: 修复前 test_ddl_guard 在钉子问法上实际失败（本日 CI 记录）;
          恢复 thief 关键词的在场模拟同样复现
```

## 规则表

CLAUDE.md 末尾新增“规则与强制手段对照表”,六条规则各配强制层与来源事故;
后续每次纠错在表中加一行,规则失配强制手段即视为重复、升级处置层。

## 验证

```
tests/test_collision_guards.py + 台账消费方套件:
============================= 75 passed in 7.51s ==============================
All checks passed!   (ruff)
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
