# 敏感数据 Agent 使用指南 (PII Scan · Mask · Verify)

面向数仓 SQL 脚本的敏感数据「发现 → 处置 → 验证」闭环工具。全链路确定性：
不连接数据库、不执行任何语句、不需要 LLM 或 API key。

- **Web UI**：首页 → 敏感数据扫描（`/pii`）
- **CLI**：`seatunnel-agent pii`
- **REST**：`POST /api/pii/scan` / `POST /api/pii/mask`（目录白名单
  `PII_API_ALLOWED_DIRS`）
- **MCP**：统一工具箱 `seatunnel-agent mcp` 的 `pii_scan` / `pii_mask`
- **编排器**：自然语言「查敏感列」「这段 SQL 帮我脱敏」可直达，支持
  `pii_scan → pii_mask` 组合链

## 能力分层

| 层 | 回答的问题 | 输出 |
|---|---|---|
| 扫描（scan） | 敏感列在哪、扩散到了哪 | 分级 Markdown 报告（high/medium/low），含未脱敏传播边 |
| 处置（mask） | 该执行什么 | 按类别脱敏的 `CREATE OR REPLACE VIEW <table>_masked` 脚本 |
| 验证（coverage） | 方案覆盖了多少 | 已覆盖/未覆盖发现对账 + 未脱敏边 before→after |

## 发现：命名规则 × 字段血缘

列清单来自两处合并：`CREATE TABLE` 的列名/类型/注释（中文注释关键词也参与
匹配），以及 INSERT…SELECT 血缘里出现的列。内置 11 类规则（手机号、身份证、
银行卡、护照、邮箱、姓名、住址、工资、生日、车牌、IP），命中后沿列级血缘
下钻 5 层：传播表达式套了 `md5()/mask()/substr()` 等视为已脱敏，可逆编码
（hex/base64）不算；明文直拷会抬升严重度。

自定义规则（追加、不覆盖内置）：

```yaml
# my_rules.yaml
rules:
  - category: wechat
    severity: high
    name_patterns: ["(^|_)wechat(_?id)?(_|$)"]
    comment_keywords: ["微信"]
```

## 处置：脱敏视图生成

对每张解析到 DDL 的命中表，按原列序生成完整视图——未命中列原样透传，
命中列替换为类别表达式（hive/spark 共有函数，可直接执行）：

| 类别 | 表达式效果 |
|---|---|
| 手机号 | 留前 3 后 4：`138****5678` |
| 身份证 | 留前 6 后 4 |
| 银行卡 | 仅留后 4 |
| 邮箱 | 首字母 + 域名：`z***@example.com` |
| 工资 | 置 NULL（数值无法截断脱敏） |
| 自定义/未知类别 | `md5()` 单向哈希（保 join 不保明文） |

仅出现在血缘、没有 DDL 的表拿不到完整列清单，降级为列表达式片段并给出
警告。`--min-confidence high` 跳过弱命中（如裸 `name` 列）。

## 验证：覆盖回验与 CI 门禁

每份方案尾部附覆盖对账；`--fail-on` 在 `--mask` 模式下是**处置感知**的：
已被视图覆盖的发现视为已处置，只有未覆盖的高危才让流水线变红。

```bash
seatunnel-agent pii --dir warehouse_sql/                      # 扫描报告
seatunnel-agent pii --dir warehouse_sql/ -F json --fail-on high   # 扫描门禁
seatunnel-agent pii --dir warehouse_sql/ --mask -o masked_views.sql
seatunnel-agent pii --dir warehouse_sql/ --mask --fail-on high    # 处置感知门禁
```

典型 CI 片段：

```yaml
- name: PII gate (treatment-aware)
  run: seatunnel-agent pii --dir sql/ --mask --fail-on high
```

## 边界与注意

- 覆盖判定假设消费方切换到 `*_masked` 视图；是否真的切换属于管控面，
  超出本 agent 的静态边界。
- 脱敏宽度按中国大陆常见格式假设（11 位手机 / 18 位身份证）；其他格式
  截断位置不精确，但输出仍不可逆。
- 演示数据 `examples/pii_demo/`；其完整方案钉死在
  `examples/pii_demo_masked.golden.sql`（黄金文件在目录外，避免扫描吃进
  自身输出）。有意变更输出后用测试 docstring 里的命令重生成。

---

# PII Agent Guide (English)

A deterministic find → fix → verify loop for sensitive data in warehouse
SQL. No database connection, nothing executed, no LLM required.

**Surfaces**: Web UI `/pii` · CLI `seatunnel-agent pii` · REST
`/api/pii/{scan,mask}` (directory-whitelisted) · MCP tools
`pii_scan`/`pii_mask` · orchestrator-routable with a scan→mask chain.

**Find**: column names and comments (Chinese keywords included) match an
11-category rule catalog; hits are chased 5 levels down the column lineage,
with each propagation edge classified masked/unmasked (`md5`/`mask`/
`substr` families count, reversible encodings do not). Custom YAML rules
append to the built-ins.

**Fix**: for every table with parsed DDL, a full
`CREATE OR REPLACE VIEW <table>_masked` in original column order — phone
keeps 3+4 digits, national ID 6+4, bank card last 4, e-mail first letter +
domain, salary suppressed to NULL, unknown categories hash with `md5()`.
Lineage-only tables degrade to expression snippets with a warning;
`--min-confidence high` skips weak hits.

**Verify**: every plan ends with a coverage footer (covered/uncovered
findings, unmasked spread edges before → after). With `--mask`, `--fail-on`
is treatment-aware: only UNCOVERED findings at/above the level fail CI.

Demo data lives in `examples/pii_demo/`; its full plan is pinned as a
golden file outside the directory (so the scan never eats its own output).
