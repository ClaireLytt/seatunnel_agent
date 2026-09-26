# PRD · SQL 方言翻译 Agent (SQL Transpile)

> Issue: https://github.com/ClaireLytt/seatunnel_agent/issues/10
> 状态: v1 已实现 (2026-09-25) — M1/M2/M3 全部落地；方言按拍板缩为 4 个

## 1. 背景与目标

数仓迁移(Hive → Doris/StarRocks、Presto → Spark 等)时,存量 SQL 需要逐条改写,
人工改写慢且易错。本项目已依赖 sqlglot(血缘、SQL Review 均在用),其
`transpile()` 能确定性地完成大部分方言转换;LLM 只负责兜底(UDF 映射、
sqlglot 不支持的语法)和差异解释。

**目标**:输入任意方言 SQL(单条 / 文件 / 目录),输出目标方言 SQL +
不兼容点清单。**LLM 可完全关闭(`--no-llm`),确定性路径独立可用。**

**非目标(Out of Scope)**:
- 不连接任何数据库、不执行 SQL、不校验对象是否存在
- 不做语义等价性验证(执行结果对比属于 data_comparison 的范畴)
- Flink SQL 作为**目标**方言不走确定性路径(sqlglot 无 flink dialect),
  仅在 LLM 开启时提供尽力翻译,输出中明确标注 `llm-generated`

## 2. 用户与场景

| 场景 | 用户 | 输入 | 输出 |
|------|------|------|------|
| S1 数仓迁移 | 数据工程师 | Hive SQL 目录 | Doris SQL 目录 + 迁移报告 |
| S2 单条改写 | 分析师 | 粘贴一条 Presto SQL | Spark SQL + 差异说明 |
| S3 CI 检查 | 平台方 | `--format json` | 机器可读的不兼容清单 |
| S4 Review 联动 | 工程师 | SQL Review 页面结果 | 一键转目标方言(P2) |

## 3. 方言矩阵

首期(已拍板)支持 4 个方言,源/目标对等,均走确定性路径(sqlglot):

| | hive | spark | doris | starrocks |
|--|--|--|--|--|
| 源 | ✅ | ✅ | ✅ | ✅ |
| 目标 | ✅ | ✅ | ✅ | ✅ |

第二批已开放:mysql / presto(trino) / clickhouse(v1.1,按本条款扩充);
postgres 等其余方言继续按需开放。

- `--from` 可省略:sqlglot 先按 `--to` 以外的常见方言尝试解析,失败再报错
  (报告里注明"源方言为推断值")
- flink 仅出现在 `--to` 且 LLM 开启时(P2,单独用例覆盖)

## 4. 功能需求

### F1 单条/多条 SQL 翻译(P0,确定性)
- 输入:SQL 文本(可含多条,以 `;` 分隔)、源方言、目标方言
- 处理:`sqlglot.transpile(sql, read=src, write=dst, pretty=True)`
- 多条语句逐条翻译,单条失败不影响其余(错误进不兼容清单)

### F2 不兼容点清单(P0,确定性)
每条 SQL 附带结构化条目,来源三类:
1. **parse_error** — sqlglot 无法解析(行号、片段、原始报错)
2. **unsupported** — 捕获 sqlglot 的 `UnsupportedError`/warning
   (`unsupported_level=RAISE` 探测 + `WARN` 降级拿到列表)
3. **manual_check** — 规则库标注需人工确认的模式,首期内置:
   - 未知函数(不在目标方言函数表中的 UDF)
   - Hive `LATERAL VIEW explode` → 目标方言写法差异
   - `DISTRIBUTE BY / CLUSTER BY / SORT BY`
   - 分区写法差异(`PARTITION (dt='...')`)
   - 建表语句的存储格式/属性子句(`STORED AS` / `TBLPROPERTIES`)

条目字段:`{level: error|warn|info, kind, line, snippet, message, suggestion}`

### F3 批量目录翻译(P0)
- `--dir sql/ --out out/`:递归处理 `*.sql`,目录结构镜像输出
- 汇总报告:N 文件 / M 语句 / 全自动 X / 需人工 Y / 失败 Z
- `--fail-on error|warn` 供 CI 使用(退出码非 0)

### F4 LLM 兜底与解释(P1,可关)
- 仅对 F2 中 `parse_error` 与 `manual_check` 条目触发
- 产出:建议改写(标注 `llm-generated`,不覆盖确定性结果,单独呈现)+
  一段中文差异解释
- `--no-llm` / 无 API key 时完全跳过,主流程不受影响

### F5 SQL Review 联动(P2)
- Review 报告页加"转换为…"入口,带着当前 SQL 跳转 `/transpile`

## 5. 接口设计

### 5.1 模块结构(镜像 `sql_review/` 惯例)
```
src/seatunnel_agent/sql_transpile/
  __init__.py
  transpiler.py    # 核心:translate(sql, src, dst) -> TranspileResult
  rules.py         # manual_check 规则库(纯函数,好单测)
  report.py        # 文本/JSON 报告渲染
  api.py           # FastAPI router
  prompts.py       # LLM 兜底提示词
  i18n.py          # 中英文案
src/seatunnel_agent/sql_transpile_ui.py   # Gradio 页面
```

### 5.2 CLI(click,挂在现有 `cli.py`)
```bash
seatunnel-agent transpile --to doris query.sql                 # 推断源方言
seatunnel-agent transpile --from hive --to doris --dir sql/ --out doris_sql/
seatunnel-agent transpile --from presto --to spark -e "SELECT approx_distinct(uid) FROM t"
seatunnel-agent transpile --to doris --dir sql/ --format json --no-llm --fail-on error
```

### 5.3 REST API
```
POST /api/transpile/translate   {sql, from?, to, llm?: bool}
POST /api/transpile/batch       {dir, from?, to}     # 复用 lineage 的目录白名单校验
GET  /api/transpile/dialects    # 支持的方言矩阵
GET  /api/transpile/health
```

### 5.4 UI(`/transpile`,复用现有 Gradio 页面骨架)
- 左:源方言下拉(含"自动推断")、目标方言下拉、SQL 输入框、
  "翻译"按钮、目录批量入口
- 右:翻译结果(代码块,可复制)、不兼容点列表(级别着色)、
  LLM 建议区(开关可用时)
- 首页 hub 加卡片(参照 lineage 卡片的 data-en/data-zh 双语模式)

## 6. 输出示例

```
== 翻译结果 (hive → doris) ==
SELECT dt, SUM(amount) AS gmv FROM dwd.orders_di GROUP BY dt;

== 不兼容点 (1 warn / 1 info) ==
[warn] L3 未知函数 get_json_object — Doris 建议 json_extract,需人工确认
[info] L1 源 SQL 含 DISTRIBUTE BY,Doris 中已移除,请确认分桶策略

统计: 语句 2 · 全自动 1 · 需人工 1 · 失败 0
```

## 7. 非功能需求

- **确定性**:同一输入产出恒定(LLM 建议区除外);CI 中 `--no-llm` 全流程可跑
- **性能**:单条 SQL < 100ms;1000 条批量 < 30s(纯 CPU)
- **安全**:只读文件,不执行 SQL;API 目录参数走与 lineage 相同的白名单校验
- **i18n**:报告与 UI 文案中英双语,遵循现有 i18n.py 模式

## 8. 测试计划

### 8.1 单元测试(`tests/test_sql_transpile.py`,不需要 LLM/DB)
- **golden 用例**:每对重点方言(hive→doris、hive→starrocks、presto→spark、
  mysql→hive)≥ 8 条,覆盖:函数映射、类型 cast、日期函数、窗口函数、
  `LATERAL VIEW`、CTAS、INSERT OVERWRITE
- **不兼容清单**:构造 parse_error / unsupported / manual_check 各类样例,
  断言级别、行号、kind
- **多语句**:一条坏 SQL 不拖垮整批
- **批量**:tmp 目录镜像输出、统计数、`--fail-on` 退出码
- **API**:TestClient 打 4 个端点;目录白名单拒绝越权路径
- 演示数据:新增 `examples/transpile_demo/`(6~8 个 Hive SQL,
  含 2 个故意不兼容的)

### 8.2 UI 自动化(`ui_testing/cases/transpile.yaml`,TRP 组)
| 用例 | 内容 | tags |
|------|------|------|
| TRP1 | 单条 hive→doris 翻译,结果区含目标 SQL | smoke |
| TRP2 | 含 get_json_object 的 SQL,不兼容区出现 warn | smoke |
| TRP3 | 非法 SQL 报错不崩溃(text_not_contains: Traceback) | full |
| TRP4 | 切换目标方言重新翻译,结果变化 | full |
| TRP5 | 批量目录翻译统计正确(用 examples/transpile_demo) | full |
| TRP6 | LLM 建议区内容合理(ai_judge,--no-llm 时跳过) | full |

### 8.3 CI
- 纯确定性路径必须在无 API key 环境全绿(和 sql_review `--static-only` 同策略)

## 9. 里程碑

| 阶段 | 内容 | 预估 |
|------|------|------|
| M1 | transpiler + rules + report + CLI + 单测 + demo 数据 | 1 天 |
| M2 | REST API + Gradio 页面 + TRP 用例 + hub 卡片 | 1 天 |
| M3 | LLM 兜底 + 批量/--fail-on + README 双语文档 | 0.5~1 天 |

## 10. 风险与对策

| 风险 | 对策 |
|------|------|
| sqlglot 对 Doris/StarRocks 覆盖不全 | 不兼容清单兜底 + manual_check 规则可配置扩展 |
| UDF 无法自动映射 | 明确标 manual,LLM 给建议但不自动应用 |
| Flink 目标方言无确定性支持 | 首期文档明示;LLM 路径输出显著标注 |
| 用户误信翻译结果直接上线 | 报告头部固定提示"需人工复核 + 建议配合数据比对验证" |
