# SQL Code Review 功能测试文档

> 分支：`sql_review` · 更新日期：2026-09-22
>
> 覆盖范围：SQL Review 页面（UI 修复项 + 行号跳转 + URL 预填）、
> Text2SQL 集成审查卡片、`review-harness` 回放 CLI（基线对比 / LLM 缓存复用）、
> 自动化测试。

## 0. 环境准备

```bash
# 安装依赖（已装可跳过）
pip install -e .

# 启动 Web UI（含 /sqlreview 与 /text2sql 页面）
seatunnel-agent ui
# 或
python -m seatunnel_agent.cli ui
```

浏览器打开 `http://127.0.0.1:7860`。

---

## 1. SQL Review 页面 UI 修复项

### 1.1 页面滚动条（缺陷修复）

| 步骤 | 操作 | 预期结果 |
|---|---|---|
| 1 | 打开 `/sqlreview` 页面 | 页面正常渲染 |
| 2 | 在 SQL 输入框粘贴一段较长 SQL 并执行「审查」 | 生成较长的审查报告 |
| 3 | 用鼠标滚轮 / 拖动右侧滚动条向下滚动 | **整个页面可以滚动**，能看到报告底部与下载按钮，不再被锁死在一屏内 |
| 4 | 切换到其他页面（如 `/text2sql`）再切回 | 滚动行为仍然正常，其他页面布局不受影响 |

> 实现说明：全局 CSS 将 `.gradio-container` 锁定为 `100vh + overflow:hidden`；
> sqlreview 页面通过隐藏标记 `<div class="st-review-page">` +
> `body:has(.st-review-page)` 选择器解锁滚动（与历史页同一套机制）。

### 1.2 SQL 输入框一键复制（缺陷修复）

| 步骤 | 操作 | 预期结果 |
|---|---|---|
| 1 | 在 SQL 输入框输入任意 SQL | 输入框右上角出现复制按钮 |
| 2 | 点击复制按钮 | SQL 全文进入剪贴板，粘贴到别处内容一致 |

### 1.3 审查报告一键复制（缺陷修复）

| 步骤 | 操作 | 预期结果 |
|---|---|---|
| 1 | 执行一次「静态审查」或「LLM 审查」 | 报告区域右上角出现复制按钮 |
| 2 | 点击复制按钮 | 报告 Markdown 全文进入剪贴板 |
| 3 | 执行「一键修复」生成修复 SQL | 修复 SQL 代码块也带复制按钮，可一键复制 |

### 1.4 行号定位跳转（新功能）

| 步骤 | 操作 | 预期结果 |
|---|---|---|
| 1 | 用示例 SQL 执行「静态审查」 | 报告表格的「代码位置」列中「行 N」渲染为可点击链接 |
| 2 | 点击某个「行 N」链接 | 左侧 SQL 输入框滚动到该行并**选中整行**，页面平滑滚动到输入框 |
| 3 | 切换英文再审查 | 链接文案变为「Line N」，点击行为一致 |

> 实现说明：`render_report(line_links=True)` 把行号渲染为
> `[行 N](#srline-N)`，页面全局 JS 拦截该锚点点击并在
> `#sr-sql-box textarea` 中 setSelectionRange + 滚动。CLI 输出不带链接。

### 1.5 URL 参数预填（新功能）

| 步骤 | 操作 | 预期结果 |
|---|---|---|
| 1 | 打开 `/sqlreview?sql=SELECT%20*%20FROM%20t&dialect=spark` | SQL 输入框预填 `SELECT * FROM t`，方言选中 Spark SQL |
| 2 | 打开 `/sqlreview`（无参数） | SQL 输入框为空（只显示 placeholder） |

### 1.6 界面优化（新）

| 用例 | 操作 | 预期结果 |
|---|---|---|
| 报告卡片 | 执行任意审查 | 报告显示在带边框圆角卡片中，表格有边框 / 表头底色 / 隔行条纹 |
| 输入区吸顶 | 报告较长时向下滚动页面 | 左侧 SQL 输入列固定在顶部（sticky），点击「行 N」链接时输入框仍可见 |
| 清空按钮 | 点击「清空」 | SQL 输入框、报告、修复 SQL、下载按钮全部复位为初始状态 |
| 修复按钮反馈 | 完成审查后点击「生成修复 SQL（LLM）」 | 立即显示「-- 正在调用 LLM 生成修复 SQL……」且按钮置灰，LLM 返回后替换为修复 SQL 并恢复按钮；未审查时立即提示「-- 请先完成一次审查」 |
| 侧边栏拖宽 | 在 SeaTunnel / Text2SQL / 数据比对页面，拖动侧边栏右缘 | 宽度在 180–520px 间跟随鼠标，刷新后保留（localStorage）；折叠侧边栏时拖动条隐藏 |

### 1.7 回归项（原有功能不受影响）

- 静态审查：粘贴 `SELECT * FROM a JOIN b` → 报告出现「SELECT \*」与「JOIN 缺 ON」问题。
- 中英文切换：切换语言后按钮 / 报告标签跟随切换。
- 报告下载：Markdown / JSON 下载按钮仍可用。

### 1.8 多数据库方言支持（新功能）

方言下拉扩展为 10 种：Hive / Spark / Flink / MaxCompute / MySQL /
PostgreSQL / SQL Server / ClickHouse / Doris / SQLite。规则按引擎家族门控：

| 用例 | 方言 | 输入 SQL | 预期结果 |
|---|---|---|---|
| 1 | MySQL | `UPDATE users SET status = 1` | 🔴 严重：UPDATE 没有 WHERE 条件 |
| 2 | PostgreSQL | `DELETE FROM users` | 🔴 严重：DELETE 没有 WHERE 条件 |
| 3 | MySQL | `SELECT id FROM t WHERE name LIKE '%abc'` | 🟡 风险：LIKE 前导通配符（索引失效） |
| 4 | MySQL | `SELECT id FROM orders WHERE DATE(create_time) = '2026-01-01'` | 🟢 建议：WHERE 列上函数使索引失效 |
| 5 | MySQL | `SELECT id FROM t ORDER BY id LIMIT 100000, 20` | 🟡 风险：深分页 OFFSET |
| 6 | ClickHouse | `SELECT id FROM orders FINAL` | 🟡 风险：FINAL 强制读时合并 |
| 7 | MySQL | `SELECT id FROM dw.fact_order_di ORDER BY id` | 不报「缺分区过滤」「ORDER BY 无 LIMIT」（OLTP 不适用） |
| 8 | Hive | 同上 | 仍报分区过滤 + ORDER BY 无 LIMIT（大数据引擎规则保留） |
| 9 | 任意新方言 | `SELECT * FROM a JOIN b WHERE x = NULL` | 通用规则（SELECT \* / 笛卡尔积 / = NULL）照常触发 |

CLI 同步：`seatunnel-agent review -d mysql ...` 与 `review-harness -d clickhouse ...`
可直接使用新方言；`--db` 现在按方言正确映射执行器（spark→sparksql 等）。

---

## 2. Text2SQL 集成：内联审查卡片

在 Text2SQL 聊天中，每次执行 SQL 后回复末尾会追加一张「SQL 审查」卡片。

| 用例 | 操作 | 预期结果 |
|---|---|---|
| 2.1 有问题的 SQL | 在 `/text2sql` 提问，使生成的 SQL 含 `SELECT *` 或缺 LIMIT | 回复底部出现可折叠的「SQL 审查」卡片，摘要显示 `N 严重 · N 风险 · N 建议`，展开可见前 5 条问题（带严重级别徽章） |
| 2.2 干净的 SQL | 提问使生成的 SQL 规范（明确列名、有过滤条件） | 出现绿色一行卡片「SQL 审查：静态检查未发现问题」 |
| 2.3 跳转完整审查 | 点击卡片底部「完整审查 →」链接 | 新标签页打开 `/sqlreview`，**SQL 与方言已自动预填**（SQL 过长时仅打开空页面） |
| 2.4 容错 | 审查内部出错（如极端 SQL） | 卡片静默跳过，不影响查询结果展示 |
| 2.5 语言 | 切换 Text2SQL 页面语言为 English 再执行查询 | 卡片文案变为英文（"SQL Review" 等） |

---

## 3. `review-harness` CLI：回放 Text2SQL 查询日志

harness 将 `logs/text2sql_queries.jsonl` 中所有历史生成的 SQL 重新过一遍
静态审查规则，产出聚合质量报告——把真实 Text2SQL 输出变成回归测试集。

### 3.1 基本用法

```bash
# 中文 Markdown 报告（默认读取 logs/text2sql_queries.jsonl）
seatunnel-agent review-harness --lang zh

# 只回放最近 50 条，指定方言
seatunnel-agent review-harness -n 50 -d spark

# JSON 输出并保存到文件
seatunnel-agent review-harness -F json -o harness_report.json

# 提供 DDL 做 schema 感知审查 + 自定义规则
seatunnel-agent review-harness --ddl schema.sql --rules .sqlreview.yaml
```

| 用例 | 命令 | 预期结果 |
|---|---|---|
| 3.1.1 默认运行 | `seatunnel-agent review-harness --lang zh` | 输出：日志记录数 / 已审查 / 跳过 / 无问题率、按严重级别统计、高频违规规则、问题最多的查询表格 |
| 3.1.2 限制条数 | `... -n 5` | 只统计最近 5 条记录 |
| 3.1.3 JSON 格式 | `... -F json` | 输出合法 JSON（含 `clean_rate`、`entries` 等字段） |
| 3.1.4 日志不存在 | `... --log nope.jsonl` | 报错退出（UsageError），提示日志未找到 |
| 3.1.5 保存文件 | `... -o report.md` | 报告写入文件，UTF-8 编码 |

### 3.2 基线对比（`--baseline`，新功能）

跑两次 harness、对比新增 / 消失的问题，检测规则或生成器回归。

```bash
# 第一次：保存 JSON 基线
seatunnel-agent review-harness -F json -o baseline.json

# （生成一些新查询后）第二次：与基线对比
seatunnel-agent review-harness --baseline baseline.json --lang zh
```

| 用例 | 预期结果 |
|---|---|
| 有变化 | 报告末尾出现「与基线对比」：已审查数量变化、无问题率变化（带 ±%）、问题数变化（±严重/风险/建议）、新增违规规则、消失的违规规则 |
| 无变化 | 显示「与基线相比无变化」 |
| JSON 模式 | `-F json --baseline ...` 输出含 `baseline_diff` 字段 |
| 基线文件损坏 | UsageError 提示 invalid baseline file |

### 3.3 LLM 审查缓存复用（`--llm-cache`，新功能）

UI/CLI 的每次 LLM 审查都会记录到 `logs/sql_review.jsonl`（含 SQL 哈希
`sql_sha256`）。harness 加 `--llm-cache` 后，对与历史 LLM 审查完全相同的
SQL 直接复用其结果，不再调 LLM。

```bash
# 先在 /sqlreview 页面用 LLM 模式审查若干条 text2sql 生成的 SQL
seatunnel-agent review-harness --llm-cache --lang zh
```

| 用例 | 预期结果 |
|---|---|
| 有命中 | 报告出现「LLM 审查缓存复用」：命中查询数 + LLM 问题数（严重/风险/建议）；JSON 输出含 `llm` 字段 |
| 无命中（或历史日志无 `sql_sha256`） | 不显示该节，静态审查结果不受影响 |

### 3.4 CI 门禁（`--fail-on`）

```bash
# 存在"严重"问题时 exit 1（可用于 CI）
seatunnel-agent review-harness --fail-on critical
echo $?   # 有严重问题 → 1；否则 0

# 更严格：风险及以上即失败
seatunnel-agent review-harness --fail-on risk
```

| 用例 | 预期结果 |
|---|---|
| 日志中存在指定级别及以上问题 | 打印报告后 exit code = 1，stderr 提示「存在 X 及以上级别的问题」 |
| 无该级别问题 | exit code = 0 |

---

## 4. 自动化测试

```bash
# SQL Review 全量测试（含 harness 新增 10 个用例）
python -m pytest tests/test_sql_review.py -q

# 只跑 harness 相关
python -m pytest tests/test_sql_review.py -q -k harness
```

harness 覆盖的测试点：

- `iter_log_records`：跳过损坏行 / 空行 / 非 dict 行；文件不存在抛 `FileNotFoundError`
- `run_harness`：total / reviewed / skipped / clean 聚合正确；`limit`
  取最近 N 条；未知方言归一化为 hive；分类计数进入 `top_categories`
- `HarnessResult.to_dict`：字段齐全且可 JSON 序列化
- `render_harness_report`：中英文报告结构、表格内 `|` 与换行转义、
  全部通过时输出「无问题」文案且无 worst 表格
- `load_llm_cache`：同一 SQL 取最新 LLM 记录、忽略 static 记录与无哈希记录、
  文件缺失返回空
- `run_harness(llm_cache=...)`：命中条目/聚合计数、`to_dict` 的 `llm` 字段、
  报告出现「LLM 审查缓存复用」节；未传 cache 时无 `llm` 字段
- `diff_against_baseline`：新增/消失/数量变化的规则、严重级别与无问题率
  delta、无变化文案、中英文渲染
- `render_report(line_links=True)`：行号渲染为 `[行 N](#srline-N)` 链接，
  默认（CLI）不带链接
- `ReviewLogger`：日志记录含 `sql_sha256`；`sql_hash` 对首尾空白稳定

当前基线：**215 passed**（全仓 1307 passed）。

---

## 5. 已知限制

- harness 本身只做静态审查（不调 LLM、不连数据库），schema 相关规则需要
  `--ddl`；`--llm-cache` 只复用历史 LLM 结果，不会发起新的 LLM 调用。
- LLM 缓存按 SQL 精确匹配（strip 后 sha256），SQL 有任何改动即不命中；
  旧日志（本次更新前）没有 `sql_sha256`，不参与复用。
- 行号跳转仅静态审查报告可用（LLM 报告是自由文本）。
- 内联审查卡片使用会话中的数据源类型作为方言，未连接数据源时默认 hive；
  「完整审查 →」预填仅在 SQL urlencode 后 ≤ 1800 字符时携带。
- Windows GBK 控制台直接打印中文报告可能乱码，用 `-o` 保存文件即为 UTF-8。
