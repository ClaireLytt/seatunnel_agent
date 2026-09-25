# PRD · 变更影响分析 Agent (Change Impact Analysis)

> Issue: https://github.com/ClaireLytt/seatunnel_agent/issues/10
> 状态: v1 (2026-09-25)
> 前置: 数据血缘 Agent（复用其构图/遍历/快照对比能力）

## 1. 背景与目标

数仓上线评审的高频问题是"这次改动影响哪些下游表/报表"。目前只能人工在血缘页
逐表查询。本 Agent 把 **SQL 变更检测 × 血缘下游遍历** 串成一条链：输入一次
变更（两个 SQL 目录，或一个 git 基线），输出结构化的"上线影响面"报告——
哪些表/字段的口径变了、下游多少张表受影响、哪些变更是破坏性的。

**纯确定性**：不连接数据库、不执行 SQL、默认不调用 LLM（可选的 LLM 评审摘要
单独开启，且不影响确定性结论）。

**非目标（Out of Scope）**：
- 不做数据值层面的验证（那是数据比对页的职责，报告里引导跳转）
- 不做调度/任务级影响（只到表和字段粒度）
- v1 不读 Hive 元数据血缘表（只对比 SQL 目录；git 模式也是目录物化后对比）

## 2. 用户与场景

| 场景 | 输入 | 输出 |
|------|------|------|
| S1 上线评审 | 旧/新两个 SQL 目录 | 影响面报告（变更表、下游、严重度） |
| S2 CI 门禁 | `--base origin/main --sql-dir sql/` | `--fail-on error` 拦截破坏性变更 |
| S3 页面自查 | /lineage 页"变更影响"面板 | 同报告，渲染在结果区 |

## 3. 变更检测模型（全部确定性）

对旧/新两份 SQL 目录分别 `build_graph()`，然后做三层 diff：

1. **表级**：复用 `snapshot.diff_graphs()` —— 新增/移除的表与边、置信度变化
2. **字段级**：对比字段边四元组 `(src_table, src_col, dst_table, dst_col)`
   - 新增 / 移除字段边
   - **口径变更**：同一四元组的 `expression`（规范化后）或聚合标记不同
3. **影响面**：对每个"受影响目标表"，在**新图**上 `downstream_of(depth)`
   遍历下游；对被移除的表在**旧图**上遍历（它原来的消费方即断链风险）

### 严重度规则

| 级别 | 触发条件 | 典型含义 |
|------|----------|----------|
| error | 移除的表/边在旧图中存在下游消费方 | 破坏性变更，下游会断 |
| warn | 字段口径变更（expression 变化）且该表有下游 | 下游数值口径漂移 |
| info | 纯新增（表/边/字段边）、无下游的变更 | 需知晓，无风险 |

`--fail-on error|warn` 与 sql_transpile 同语义，供 CI 使用。

## 4. 接口设计

### 4.1 模块（放在血缘家族内，最大化复用）
```
src/seatunnel_agent/data_lineage/impact.py   # analyze_impact + 渲染
  ImpactResult / ChangedTable / ColumnChange (dataclass)
  build_old_graph_from_git(ref, sql_dir)     # git show 物化到临时目录
  analyze_impact(old_graph, new_graph, depth=3) -> ImpactResult
  render_impact_markdown(result, lang)       # zh/en
  impact_to_dict(result, lang)               # JSON payload
```

### 4.2 CLI
```bash
seatunnel-agent impact --old-dir examples/impact_demo/old --sql-dir examples/impact_demo/new
seatunnel-agent impact --base HEAD~1 --sql-dir sql/                  # git 基线模式
seatunnel-agent impact --old-dir old/ --sql-dir new/ -F json --fail-on error   # CI 门禁
```
`--depth`（默认 3）、`--lang zh|en`、`--format markdown|json`。
`--old-dir` 与 `--base` 二选一，都缺省时报 UsageError。

### 4.3 REST（挂在现有 lineage router 上）
```
POST /api/lineage/impact  {old_dir, new_dir, depth?, lang?}
```
目录参数复用 lineage 的 `_check_dir_allowed` 白名单（`LINEAGE_API_ALLOWED_DIRS`）。
git 模式不开放给 API（网络入口不执行 git 命令）。

### 4.4 UI（/lineage 页新增侧栏面板，不新开页面）
侧栏 accordion「变更影响分析」：旧 SQL 目录、新 SQL 目录、深度滑条、
「变更影响分析」按钮；报告渲染到主结果区（`.st-lin-main`，wait_result 可用）。
uitest 页 Agent picker 无需改动——`数据血缘` 项按路由 `/lineage` 自动收编
IMP 用例。

## 5. 演示数据 `examples/impact_demo/`

`old/`（4 条 SQL：ods→dwd→dws×2→ads）与 `new/`，差异设计成三种变更类型各一：

| 文件 | old→new 变化 | 期望检出 |
|------|--------------|----------|
| 02_dwd_to_dws_gmv.sql | `SUM(amount)` → `SUM(amount - refund_amount)` | warn 口径变更 + 新增字段边 |
| 04_dws_to_ads_report.sql | 不再 JOIN dws.user_stats | error 移除边（ads.gmv_report 在旧图有此上游） |
| 05_ads_channel.sql | 新文件：ads.channel_report | info 新增表/边 |

## 6. 报告样例（zh）

```
## 变更影响分析 (old → new)
**变更 3 处 · 受影响表 3 · 下游波及 2 · error 1 / warn 1 / info 1**

### ❌ [error] ads.gmv_report — 上游被移除
- 移除边: dws.user_stats -> ads.gmv_report
### ⚠️ [warn] dws.gmv_daily — 字段口径变更
- gmv: SUM(amount) → SUM(amount - refund_amount)
- 下游波及: ads.gmv_report (L1)
### ℹ️ [info] ads.channel_report — 新增表
> 建议配合数据比对页对受影响表做上线前后校验。
```

## 7. 测试计划

### 7.1 单元测试 `tests/test_lineage_impact.py`（无 LLM/DB/网络）
- 三种变更类型的检出与严重度（用 impact_demo 目录）
- 字段口径变更：expression 规范化（大小写/空白不误报）
- 下游波及：depth 截断、移除表走旧图
- 无变更 → 全空 + worst_level None
- git 模式：tmp_path 里 init 仓库两次 commit，验证与目录模式结论一致
- CLI：目录模式 / json / fail-on 门禁 / 参数校验
- API：白名单拒绝、正常返回、depth 参数

### 7.2 UI 自动化 `cases/impact.yaml`（IMP 组,page: /lineage）
| 用例 | 内容 | tags |
|------|------|------|
| IMP1 | old/new 目录分析,结果区含 dws.gmv_daily 与 ads.gmv_report | smoke |
| IMP2 | 新增表 ads.channel_report 以 info 呈现 | full |
| IMP3 | 不存在目录给出警告不崩溃 | full |

### 7.3 CI
无 API key 环境全绿（本 Agent 无任何 LLM 依赖路径）。

## 8. 里程碑

| 阶段 | 内容 |
|------|------|
| M1 | impact.py 核心 + 演示数据 + 单测 |
| M2 | CLI + API + /lineage 面板 + IMP 用例 |
| M3 | README 双语 + docs 更新 |

## 9. 风险与对策

| 风险 | 对策 |
|------|------|
| SQL 解析失败导致图不完整 → diff 误报 | 沿用 build_graph 的 warnings，报告头部透出两侧解析警告数 |
| git 模式在非仓库目录运行 | 明确报错并提示改用 --old-dir |
| 大目录构图慢 | build_graph(use_cache=False) 双图构建,报告耗时;深度默认 3 |
| 误当作数据验证工具 | 报告尾部固定引导"配合数据比对页校验" |
