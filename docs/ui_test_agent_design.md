# UI 测试 Agent — PRD 与技术方案

> 版本 v1.0 · 2026-09-24 · 状态:待评审
> 关联:`examples/dc_test_checklist.html`(75 项人工验收清单)、issue #20

---

# 第一部分 · PRD

## 1. 背景

项目已有 6 个 Gradio 页面(SeaTunnel 配置、Text2SQL、历史、收藏、Schema 浏览、数据对比),
仅数据对比一页就有 75 项人工验收用例。当前测试现状:

- **pytest 只覆盖纯函数层**(comparator/differ/exporter 等,452 项),UI 层零覆盖;
- **gradio_client API 测试有盲区**:本项目曾出现"API 调用全绿、真实浏览器必崩"的 bug
  (隐藏组件在浏览器提交 `None`,API 却可传 `""`),只有真实浏览器能暴露;
- **人工回归成本高**:每次改动跑完 75 项清单约 2~3 小时,实际执行率低,回归漏测频发
  (近期连续三轮"search 没反应"往返即为例证:`.change` 事件在真实浏览器不触发,
  headless 自动化当时立即就能发现)。

结论:需要一个**驱动真实浏览器**的 UI 测试 Agent,把人工清单变成可重复执行的自动回归。

## 2. 目标与非目标

### 2.1 目标

| # | 目标 | 度量 |
|---|------|------|
| G1 | 数据对比页核心路径自动回归 | 冒烟集 ≥20 用例,单轮 <5 分钟,全自动出报告 |
| G2 | 用自然语言写用例,无需写代码 | YAML 里写中文步骤即可执行(LLM 兜底定位) |
| G3 | 模糊预期可判定 | "差异单元格高亮"这类预期由 LLM judge 给出判定+依据 |
| G4 | 失败可诊断 | 失败用例自动附:截图、页面摘要、服务端 traceback、LLM 归因 |
| G5 | 与人工清单同源 | 用例库结构与 75 项清单一一对应,编号一致(A1/B3/C3…) |

### 2.2 非目标(v1 明确不做)

- ❌ 不做录制回放(recorder);
- ❌ 不做视觉像素级 diff(仅语义断言+截图留档);
- ❌ 不覆盖 Text2SQL 聊天页的 LLM 对话质量(那是模型评测,不是 UI 测试);
- ❌ 不做分布式/并行执行(单浏览器串行足够,用例总量 <200);
- ❌ v1 不接 CI(留接口,M3 再接)。

## 3. 用户与场景

| 角色 | 场景 |
|------|------|
| 开发者(主用户) | 改完代码跑 `python -m seatunnel_agent.ui_testing run --suite smoke`,5 分钟拿到回归结论 |
| 开发者 | 修 bug 后只跑单条:`... run --case A5` |
| 验收者 | 打开「UI 测试」页面,勾选套件点运行,看报告,对失败项截图直接反馈 |
| 用例作者 | 在 `ui_testing/cases/*.yaml` 用中文加一条用例,不写一行 Python |

## 4. 功能需求

优先级:P0 = v1 必须;P1 = v1 尽量;P2 = 后续。

### F1 · 用例库(P0)

- 用例为 YAML 文件,按模块分文件(`connect.yaml`、`search.yaml`、`compare.yaml`…);
- 每条用例含:`id`(与人工清单编号一致)、`title`、`tags`、`steps`、`expect`;
- `steps` 支持两种写法,**可混用**:
  - **脚本步骤**(确定性,免 token):`click: 连接`、`fill: {主机: 1.2.3.4}`、`press: Tab`;
  - **自然语言步骤**(LLM 执行):`ai: 打开选择表下拉框,输入 user,确认只显示 3 张表`;
- `expect` 同样两级:`assert`(确定性断言)与 `ai_judge`(LLM 判定);
- 标签体系:`smoke`(冒烟)、`full`(全量)、`hive`(需真实 Hive,默认跳过)、
  `sqlite`(用内置演示库,默认数据源)、`slow`(定时任务等 >1min 用例)。

### F2 · 确定性执行器(P0)

- 动作 DSL 全集见技术方案 §4;
- 每步默认自动等待(元素出现 ≤10s、Gradio 请求静默 ≤15s),失败自动重试 1 次;
- 每步产出结构化 StepLog(动作、定位方式、耗时、结果);失败时自动截图。

### F3 · LLM 驱动执行(P0)

- 对 `ai:` 步骤启动 agent 循环:**观察(页面摘要)→ 决策(工具调用)→ 执行 → 再观察**;
- 工具集 = F2 的动作 DSL + `read_page`(重新观察)+ `done`(报告步骤完成/失败);
- 单个 `ai:` 步骤限 8 轮工具调用、30k token 预算,超限即判 ERROR(防失控烧钱);
- 复用项目 `LLMClient`(Anthropic/OpenAI 双通道,配置走现有 `.env` 的 LLM_*)。

### F4 · LLM 模糊断言 judge(P0)

- 输入:预期文本 + 页面摘要(+ P1:截图,走多模态);
- 输出:`{verdict: pass|fail, reason: "..."}`,reason 写入报告;
- judge 与执行 agent 分离(单轮调用,无工具),保证判定不受执行上下文污染。

### F5 · 测试报告(P0)

- 每轮运行产出 `runs/<时间戳>/`:`report.html`(风格复用验收清单页)+
  `result.json`(机器可读)+ `shots/`(截图);
- 报告项:总览(通过/失败/错误/跳过、耗时、token 消耗),逐用例:步骤日志、
  断言明细、失败截图、服务端日志摘录、LLM 归因(P1);
- 结果四态:`PASS` / `FAIL`(断言不过)/ `ERROR`(执行异常)/ `SKIP`(标签不满足)。

### F6 · 环境管理(P0)

- Runner 自动以子进程启动被测应用在**专用端口 7912**(可配),从不触碰 7860
  (7860 是开发者常驻会话,历史上误杀过);
- 默认数据源:**SQLite 演示库**——运行前把 `dc_test_*` 十张表种子进
  `config/uitest_demo.db`(与 Hive 脚本同一套数据,断言值不变),用例无外部依赖;
- `hive` 标签用例读 `.env` 的 HIVE_*,连不上则整组 SKIP 而非 FAIL;
- 结束后:kill 子进程、可选清理种子库;中途 Ctrl+C 保证子进程不泄漏。

### F7 · CLI(P0)与 Gradio 页面(P1)

- CLI:
  ```
  python -m seatunnel_agent.ui_testing run --suite smoke        # 按标签跑
  python -m seatunnel_agent.ui_testing run --case A5 B3         # 指定用例
  python -m seatunnel_agent.ui_testing run --suite full --headed  # 有头模式调试
  python -m seatunnel_agent.ui_testing list                     # 列出用例
  ```
- Gradio 页(`/uitest`,P1):套件多选 → 运行(streaming 进度)→ 内嵌报告 + 下载。

### F8 · 失败诊断(P1)

- FAIL/ERROR 时收集:失败瞬间截图、页面摘要、被测应用 stdout/stderr 尾部 200 行;
- LLM 归因:输入上述材料,输出"疑似前端问题/后端异常/用例过期/环境问题"分类 + 一句话原因;
- 报告中失败项直接展示归因,人工只需复核。

### F9 · 用例迁移(P0,一次性)

- 把 75 项人工清单中**可自动化的 ≥55 项**迁移为 YAML(编号一致);
- 明确不自动化并在清单标注 `manual` 的:Q1/Q2(本地文件落盘验证)、S4(外部 webhook)、
  Q4(window.open 新窗口内容)、B2(拖拽 resize 手柄,browser resize 事件不可靠)等 ≤10 项。

## 5. 交互与流程

```
开发者                Runner                     被测应用(7912)         LLM
  │ run --suite smoke   │                            │                  │
  ├────────────────────▶│ 种子 SQLite 数据            │                  │
  │                     ├── 子进程启动 app ──────────▶│                  │
  │                     │ 等待 / 就绪探测              │                  │
  │                     │ for case in suite:          │                  │
  │                     │   脚本步骤 → Playwright ────▶│                  │
  │                     │   ai: 步骤 → 观察摘要 ───────┼─────────────────▶│
  │                     │   ◀───────── 工具调用(click/fill/…) ───────────┤
  │                     │   assert / ai_judge ────────┼─────────────────▶│
  │   report.html       │ 汇总 → 渲染报告              │                  │
  │◀────────────────────┤ kill 子进程                 │                  │
```

## 6. 非功能需求

| 维度 | 要求 |
|------|------|
| 稳定性 | 冒烟集连续 10 轮无 flaky(同代码同数据结果一致);所有等待显式化,禁止裸 sleep |
| 性能 | 脚本用例平均 <8s;`ai:` 步骤平均 <30s;冒烟集(20 例)<5min |
| 成本 | 纯脚本用例 0 token;冒烟集 LLM 消耗 <100k token/轮(约 ¥1 级) |
| 安全 | 报告与日志对密码/API key 脱敏;测试库仅 `dc_test_*` 前缀表;绝不连 7860 |
| 可移植 | Windows(开发机)与 Linux 均可跑;headless 默认,`--headed` 调试 |

## 7. 里程碑

| 阶段 | 内容 | 交付 |
|------|------|------|
| M1(3~4 天) | 框架:models/DSL/Gradio 适配层/env/runner/报告 + 20 条冒烟用例(纯脚本) | CLI 跑通冒烟集,报告可看 |
| M2(3~4 天) | LLM:agent 循环 + judge + `ai:` 步骤;迁移至 ≥55 用例 | 全量套件可跑,模糊断言可判 |
| M3(2~3 天) | 失败归因、Gradio 页面、pytest 桥接(`pytest -m uitest`)、文档 | 验收 & 演示 |

## 8. 验收标准

1. `run --suite smoke` 在干净环境(无 Hive、无人工干预)一次通过;
2. 人为注入三类 bug 各能被抓到:①把 connect 输出接错组件(前端错)
   ②把 `(host or "")` 守卫去掉(后端崩)③改掉一条 i18n 文案(断言 FAIL);
3. `ai:` 步骤在不给任何选择器提示的情况下完成 B3(下拉搜索)用例;
4. 报告中每个失败项都有截图与可读原因;
5. 连续 10 轮冒烟无 flaky。

## 9. 风险与对策

| 风险 | 对策 |
|------|------|
| Gradio 版本升级改 DOM 结构 | 定位收敛在适配层一个文件;定位策略带降级链;升级后只改一处 |
| LLM 定位不稳/幻觉点错 | `ai:` 仅限少数用例;工具执行前校验元素存在;失败重观察重试 1 次;预算硬顶 |
| 测试与开发端口/库互踩 | 专用端口 7912 + 专用 `uitest_demo.db`;启动前探测端口占用即换 |
| SQLite 与 Hive 行为差异(方言) | 断言值来自同一套种子数据;方言差异类用例打 `hive` 标签走真库 |
| Windows 子进程残留 | `atexit` + `taskkill /T`;runner 崩溃路径统一走 finally |
| 定时任务类用例拖慢全量 | `slow` 标签独立套件,默认不进 smoke/full |

---

# 第二部分 · 技术方案

## 1. 架构总览

```
src/seatunnel_agent/ui_testing/
├── __init__.py
├── __main__.py          # CLI 入口(run / list)
├── models.py            # TestCase / Step / Assertion / StepLog / CaseResult / RunResult
├── loader.py            # YAML 用例加载 + 校验 + 标签过滤
├── env.py               # 被测应用子进程管理 + SQLite 种子数据
├── page.py              # ★ Gradio 页面适配层(定位/动作/观察,全部踩坑收敛于此)
├── actions.py           # 动作 DSL → page 调用的分发器
├── asserts.py           # 确定性断言引擎
├── agent.py             # ★ LLM 执行循环(ai: 步骤)
├── judge.py             # LLM 模糊断言
├── diagnose.py          # 失败归因(P1)
├── report.py            # HTML + JSON 报告
├── runner.py            # 编排:套件 → 用例 → 步骤 → 结果
├── seed_sqlite.py       # dc_test_* 十表种子(与 examples/dc_hive_test_data.sql 同数据)
└── cases/
    ├── connect.yaml     # A 组
    ├── sidebar.yaml     # B 组
    ├── compare.yaml     # C/D/E 组
    ├── profile_checksum.yaml   # F/G/H/I/J/K/L/M/N 组
    ├── batch_sql_report.yaml   # O/P/Q 组
    ├── misc.yaml        # R/S/T/U/V/W/X 组
    └── _manual.yaml     # 标注不自动化的用例(报告中列为 MANUAL)
```

依赖:`playwright`(已装)、`pyyaml`(已是间接依赖,显式加入)、复用 `LLMClient`。

**分层原则(最重要的架构决策)**:LLM 只出现在三个窄口——`ai:` 步骤执行、
`ai_judge` 断言、失败归因。主干(启动、定位、动作、硬断言、报告)全部确定性,
保证稳定与零成本;LLM 是"增强",不是"地基"。

## 2. 数据模型(models.py,完整代码)

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Literal

Verdict = Literal["PASS", "FAIL", "ERROR", "SKIP", "MANUAL"]

@dataclass
class Step:
    """一条步骤:script 二选一 —— action(确定性)或 ai(自然语言)。"""
    action: str | None = None          # click / fill / press / select / goto / wait ...
    args: dict[str, Any] = field(default_factory=dict)
    ai: str | None = None              # 自然语言指令,交给 agent 循环
    note: str = ""                     # 报告中展示的人话描述

@dataclass
class Assertion:
    kind: str                          # text_contains / value_is / options_are /
                                       # options_count / status_ok / status_error /
                                       # visible / hidden / ai_judge
    args: dict[str, Any] = field(default_factory=dict)
    note: str = ""

@dataclass
class TestCase:
    id: str                            # 与人工清单一致:A1 / B3 / C3 ...
    title: str
    tags: list[str] = field(default_factory=list)   # smoke/full/hive/sqlite/slow/manual
    page: str = "/datacompare"         # 起始路由
    setup: list[Step] = field(default_factory=list)   # 前置(如:双侧连接)
    steps: list[Step] = field(default_factory=list)
    expect: list[Assertion] = field(default_factory=list)
    timeout_s: int = 60                # 单用例硬顶

@dataclass
class StepLog:
    desc: str
    ok: bool
    elapsed_ms: int
    detail: str = ""                   # 定位方式 / agent 轮数 / 错误摘要
    screenshot: str | None = None      # 相对 runs/<ts>/ 的路径

@dataclass
class CaseResult:
    case_id: str
    title: str
    verdict: Verdict
    steps: list[StepLog] = field(default_factory=list)
    asserts: list[StepLog] = field(default_factory=list)
    reason: str = ""                   # FAIL/ERROR 一句话原因(judge/归因可覆写)
    tokens: int = 0
    elapsed_ms: int = 0

@dataclass
class RunResult:
    started_at: str
    suite: str
    cases: list[CaseResult] = field(default_factory=list)
    app_log_tail: str = ""
    def counts(self) -> dict[str, int]:
        out = {"PASS": 0, "FAIL": 0, "ERROR": 0, "SKIP": 0, "MANUAL": 0}
        for c in self.cases:
            out[c.verdict] += 1
        return out
```

## 3. 用例 YAML 规范与真实示例

### 3.1 规范

```yaml
- id: <清单编号>
  title: <一句话>
  tags: [smoke, sqlite]        # 必含 sqlite 或 hive 之一
  page: /datacompare           # 可省,默认 /datacompare
  setup:                       # 可省;支持 use 引用共享前置(见 3.3)
    - use: connect_both_sqlite
  steps:
    - click: 连接               # 缩写形式,等价 {action: click, args: {target: 连接}}
    - fill: {主机: 1.2.3.4}
    - press: {keys: Tab, in: 主机}
    - select: {表: dc_test_orders_a, side: A}
    - ai: 打开 B 侧选择表下拉框,输入 user,从结果中点击 user_login
  expect:
    - status_error: {side: A}                      # 状态框呈 ❌
    - text_contains: {in: 状态, side: A, text: "端口号必须是数字"}
    - options_count: {of: 选择表, side: A, n: 3}
    - ai_judge: 样本表格中 id=3 的 amount 单元格有差异高亮
```

缩写规则:单键映射 `{动作: 值}` 展开为 `args.target=值`;`side` 缺省为 `A`。
loader 负责展开与 schema 校验(未知动作/断言直接报错,防手滑)。

### 3.2 真实用例示例(对应清单 A4 / A5 / B3 / C3 / E1)

```yaml
- id: A4
  title: 端口非法给出明确错误
  tags: [smoke, sqlite]
  steps:
    - select_ds: {value: Hive SQL, side: A}
    - fill: {主机: 127.0.0.1, 端口: abc}
    - click: {target: 连接, side: A}
  expect:
    - status_error: {side: A}
    - text_contains: {in: 状态, side: A, text: 端口号必须是数字}

- id: A5
  title: Tab 填入灰色占位默认值
  tags: [smoke, sqlite]
  steps:
    - clear: {target: 主机, side: A}
    - press: {keys: Tab, in: 主机, side: A}
    - clear: {target: 端口, side: A}
    - press: {keys: Tab, in: 端口, side: A}
  expect:
    - value_is: {of: 主机, side: A, value: 10.0.0.1}
    - value_is: {of: 端口, side: A, value: "10000"}

- id: B3
  title: 下拉框内模糊搜索
  tags: [smoke, sqlite]
  setup: [{use: connect_both_sqlite}]
  steps:
    - dropdown_type: {of: 选择表, side: A, text: dc_test_orders}
  expect:
    - options_are: {of: 选择表, side: A,
                    values: [dc_test_orders_a, dc_test_orders_b]}

- id: C3
  title: 行数对比呈现 10 vs 9 差异
  tags: [smoke, sqlite]
  setup:
    - use: connect_both_sqlite
    - select: {表: dc_test_orders_a, side: A}
    - select: {表: dc_test_orders_b, side: B}
  steps:
    - click: 行数对比
    - wait_result: {}
  expect:
    - text_contains: {in: 结果区, text: "10"}
    - text_contains: {in: 结果区, text: "9"}
    - ai_judge: 结果卡片明确标记行数不一致(红色/未通过语义)

- id: E1
  title: 主键对比找出缺失/多出/修改
  tags: [full, sqlite]
  setup:
    - use: connect_both_sqlite
    - select: {表: dc_test_orders_a, side: A}
    - select: {表: dc_test_orders_b, side: B}
    - fill: {主键列: id}
  steps:
    - click: 样本数据
    - wait_result: {}
  expect:
    - ai_judge: >
        基于主键的对比结果应包含:B 侧缺失 id=9 和 id=10、
        B 侧多出 id=11、id=3 与 id=5 标记为修改行。
```

### 3.3 共享前置(fixtures)

`cases/_fixtures.yaml` 定义可复用步骤组,`use:` 引用:

```yaml
connect_both_sqlite:
  - select_ds: {value: SQLite, side: A}
  - fill: {数据库: config/uitest_demo.db, side: A}
  - click: {target: 连接, side: A}
  - wait_status_ok: {side: A}
  - select_ds: {value: SQLite, side: B}
  - fill: {数据库: config/uitest_demo.db, side: B}
  - click: {target: 连接, side: B}
  - wait_status_ok: {side: B}
```

## 4. 动作 DSL 全集(actions.py 分发表)

| 动作 | 参数 | 语义 |
|------|------|------|
| `goto` | path | 导航到路由并等 domcontentloaded |
| `click` | target, side? | 点按钮(按可见文本) |
| `fill` | {标签: 值, ...}, side? | 逐个填输入框(按 label/placeholder) |
| `clear` | target, side? | 清空输入框(全选+Backspace,真实按键) |
| `press` | keys, in?, side? | 焦点到某输入框后按键(Tab/Escape/Enter…) |
| `select_ds` | value, side | 数据源类型下拉选择(label 精确匹配) |
| `select` | 表: 值, side | 表下拉:点开→输全名→点精确项 |
| `dropdown_type` | of, text, side? | 只在下拉输入过滤文本,不选中(配 options_* 断言) |
| `check` | target, on | 勾/去勾复选框(如 启用脱敏) |
| `open_accordion` | target | 展开手风琴(校验和/分区比对/质量规则…) |
| `wait_status_ok` | side | 等状态框出现 ✅(默认 20s,连接类专用) |
| `wait_result` | timeout? | 等结果区从"加载中"稳定(HTML 连续 1s 不变) |
| `wait` | ms | 兜底显式等待(用例里出现须写 note 说明原因) |
| `screenshot` | name? | 主动截图存档 |

## 5. Gradio 页面适配层(page.py)—— 全部踩坑收敛于此

这是稳定性的核心。**本仓库已实测确认**的 Gradio 6 行为,全部固化为适配层逻辑:

| # | 事实(本会话实测) | 适配层对策 |
|---|------------------|-----------|
| 1 | `gr.Textbox` 渲染为 `<textarea>`,不是 `<input>` | 文本框定位统一 `textarea` 选择器 |
| 2 | 下拉框是 `<input aria-expanded>` + `ul[role=listbox]` | 下拉三步:click→type→点 `li` 精确项 |
| 3 | `wait_until="networkidle"` 永不触发(SSE 长连) | 一律 `domcontentloaded` + 显式等待 |
| 4 | 隐藏组件从浏览器提交 `None`(API 是 "") | 正是要测的回归点(用例 X4) |
| 5 | 打字触发 `.input`,程序化 fill("") 不触发 | `clear` 用真实按键(Ctrl+A+Backspace) |
| 6 | 下拉输入框有内容时原生过滤选项 | `options_*` 断言前先清空下拉输入再取全集 |
| 7 | Hive 连接 10~15s | `wait_status_ok` 默认 20s,轮询状态文本 |
| 8 | 页面按钮可能中英双语 | 定位表同时登记 en/zh 文案,двух先 zh 后 en |

```python
from __future__ import annotations
from playwright.sync_api import Page, Locator

# 中英文案对照:UI 语言无论切到哪边都能定位。
# key 是用例里的"人话名",与 data_comparison/i18n.py 保持同步。
LABELS: dict[str, tuple[str, ...]] = {
    "连接":     ("连接", "Connect"),
    "主机":     ("主机地址", "Host"),
    "端口":     ("端口", "Port"),
    "数据库":   ("数据库", "Database"),
    "状态":     ("状态", "Status"),
    "选择表":   ("选择表", "Select Table"),
    "行数对比": ("行数对比", "Row Count"),
    "样本数据": ("样本数据", "Sample Data"),
    "主键列":   ("主键列", "Key Column(s)"),
    "启用脱敏": ("启用脱敏", "Enable Masking"),
    # ……迁移用例时按需补全,集中一处
}

class DCPage:
    """数据对比页适配。side: 'A' | 'B' | None(全局区)。"""

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base = base_url

    # ── 导航与区域 ──
    def goto(self, path: str = "/datacompare") -> None:
        self.page.goto(self.base + path, wait_until="domcontentloaded")
        self.page.wait_for_selector(".st-dc-sidebar", timeout=15_000)

    def _panel(self, side: str | None) -> Locator:
        """A/B 面板 = 侧边栏第 1/2 个 Column;None = 整页。"""
        if side is None:
            return self.page.locator("body")
        idx = 0 if side.upper() == "A" else 1
        return self.page.locator(".st-dc-sidebar > div > div").nth(idx)

    # ── 定位链:label → placeholder → 按钮文本,全部走文案对照表 ──
    def textbox(self, name: str, side: str | None = "A") -> Locator:
        panel = self._panel(side)
        for text in LABELS.get(name, (name,)):
            loc = panel.locator(
                f"label:has(span:text-is('{text}')) textarea")
            if loc.count():
                return loc.first
            loc = panel.locator(f"textarea[placeholder='{text}']")
            if loc.count():
                return loc.first
        raise LookupError(f"textbox not found: {name} (side={side})")

    def button(self, name: str, side: str | None = None) -> Locator:
        panel = self._panel(side)
        for text in LABELS.get(name, (name,)):
            loc = panel.locator(f"button:text-is('{text}')")
            if loc.count():
                return loc.first
        raise LookupError(f"button not found: {name}")

    def dropdown_input(self, name: str, side: str | None = "A") -> Locator:
        panel = self._panel(side)
        for text in LABELS.get(name, (name,)):
            loc = panel.locator(
                f"label:has(span:text-is('{text}')) input")
            if loc.count():
                return loc.first
        raise LookupError(f"dropdown not found: {name}")

    # ── 动作 ──
    def clear_and_type(self, name: str, value: str, side="A") -> None:
        box = self.textbox(name, side)
        box.click()
        self.page.keyboard.press("Control+a")
        self.page.keyboard.press("Backspace")     # 真实按键,触发 .input
        if value:
            box.type(value, delay=20)

    def dropdown_options(self, name: str, side="A") -> list[str]:
        inp = self.dropdown_input(name, side)
        inp.click()
        self.page.keyboard.press("Control+a")
        self.page.keyboard.press("Backspace")     # 清掉原生过滤残留(踩坑 #6)
        self.page.wait_for_timeout(300)
        items = self.page.locator("ul[role='listbox'] li")
        vals = [items.nth(i).inner_text().strip().lstrip("✓\n")
                for i in range(items.count())]
        self.page.keyboard.press("Escape")
        return vals

    def select_table(self, value: str, side="A") -> None:
        inp = self.dropdown_input("选择表", side)
        inp.click()
        inp.type(value, delay=20)                 # 原生过滤到精确项
        self.page.locator(
            f"ul[role='listbox'] li:text-is('{value}')").first.click()

    # ── 等待 ──
    def wait_status(self, side="A", ok=True, timeout_ms=20_000) -> str:
        mark = "✅" if ok else "❌"
        box = self.textbox("状态", side)
        self.page.wait_for_function(
            "(el, m) => el.value.includes(m)", arg=[box.element_handle(), mark],
            timeout=timeout_ms)
        return box.input_value()

    def wait_result_stable(self, timeout_ms=30_000) -> None:
        """结果区 HTML 连续 1s 不变视为渲染完成(Gradio 无全局 loading 信号)。"""
        self.page.wait_for_function(
            """() => {
                const el = document.querySelector('.st-dc-result, .prose');
                if (!el) return false;
                const now = el.innerHTML;
                if (window.__uitest_last === now) {
                    return (Date.now() - window.__uitest_t) > 1000;
                }
                window.__uitest_last = now; window.__uitest_t = Date.now();
                return false;
            }""", timeout=timeout_ms)

    # ── 观察(给 LLM 的页面摘要,≤4k tokens)──
    def digest(self) -> str:
        return self.page.evaluate(_DIGEST_JS)
```

> 注:`.st-dc-result` 若与实际结果容器类名不符,M1 落地时以真实 DOM 为准调整——
> 全项目仅此文件允许出现选择器,其余模块一律通过 DCPage 方法操作。

`_DIGEST_JS` 输出结构化文本摘要(不是原始 DOM),示例:

```
[PANEL A] 数据源类型=Hive SQL | 主机="180.184.31.191" | 端口="10000" |
          数据库="cladata" | 状态="✅ Hive SQL ... 9 tables loaded"
[PANEL A] 选择表: value="user_login" options(9)=[course, room_online, ...]
[BUTTONS] 连接(A) 连接(B) 结构对比 行数对比 样本数据 聚合对比 全部对比 ...
[ACCORDIONS] 预设(收起) 校验和(收起) 分区比对(展开) ...
[RESULT 1200chars] Count (A): 10 | Count (B): 9 | ✗ Mismatch ...
```

实现:遍历可见的 label+值、按钮文本、手风琴标题+开合、结果区 innerText 截断 1200 字。

## 6. 确定性执行器与断言(runner.py / asserts.py)

```python
# runner.py 主循环(节选)
def run_case(case: TestCase, dc: DCPage, llm: UITestLLM | None,
             shots_dir: Path) -> CaseResult:
    res = CaseResult(case.id, case.title, "PASS")
    t0 = time.time()
    try:
        dc.goto(case.page)
        for step in [*case.setup, *case.steps]:
            log = (run_ai_step(step, dc, llm)      # F3,LLM 循环
                   if step.ai else
                   run_script_step(step, dc))       # F2,确定性
            res.steps.append(log)
            if not log.ok:
                res.verdict = "ERROR"
                res.reason = f"步骤失败: {log.desc} — {log.detail}"
                log.screenshot = snap(dc, shots_dir, case.id)
                return res
        for a in case.expect:
            log = (run_judge(a, dc, llm)            # F4
                   if a.kind == "ai_judge" else
                   run_assert(a, dc))               # 确定性断言
            res.asserts.append(log)
            if not log.ok:
                res.verdict = "FAIL"
                res.reason = res.reason or log.detail
                log.screenshot = snap(dc, shots_dir, case.id)
    except Exception as e:                          # 兜底:异常≠测试失败,是 ERROR
        res.verdict = "ERROR"
        res.reason = f"{type(e).__name__}: {e}"
    finally:
        res.elapsed_ms = int((time.time() - t0) * 1000)
    return res
```

断言实现要点(asserts.py):

- `text_contains {in, side?, text}`:`in=状态` 读 textbox value;`in=结果区` 读
  结果容器 innerText;统一 `casefold` 后包含判断;
- `value_is {of, side, value}`:textbox/下拉 input 的 `input_value()` 精确等;
- `options_are / options_count`:走 `dropdown_options()`(内部已处理原生过滤残留);
- `status_ok / status_error {side}`:状态值含 ✅ / ❌;
- `visible / hidden {target}`:元素可见性(X4 用:SQLite 时主机/端口隐藏);
- 每条断言失败信息必须含**实际值**(`期望包含'端口号必须是数字',实际='❌ Connection refused'`)。

## 7. LLM 执行循环(agent.py)

### 7.1 工具 schema(Anthropic 格式,经 LLMClient 自动转 OpenAI)

```python
UI_TOOLS = [
  {"name": "click",
   "description": "点击按钮。target 为按钮可见文本(中或英)。",
   "input_schema": {"type": "object", "properties": {
       "target": {"type": "string"}, "side": {"enum": ["A", "B", None]}},
       "required": ["target"]}},
  {"name": "fill",
   "description": "清空并输入文本框。name 是输入框标签,如 主机/端口/主键列。",
   "input_schema": {"type": "object", "properties": {
       "name": {"type": "string"}, "value": {"type": "string"},
       "side": {"enum": ["A", "B"]}}, "required": ["name", "value"]}},
  {"name": "dropdown",
   "description": "操作下拉框:先输入 text 过滤,pick 非空则点击该精确选项。",
   "input_schema": {"type": "object", "properties": {
       "name": {"type": "string"}, "text": {"type": "string"},
       "pick": {"type": "string"}, "side": {"enum": ["A", "B"]}},
       "required": ["name"]}},
  {"name": "press", "description": "按键,如 Tab / Escape / Enter。",
   "input_schema": {"type": "object", "properties": {
       "keys": {"type": "string"}, "in_box": {"type": "string"},
       "side": {"enum": ["A", "B"]}}, "required": ["keys"]}},
  {"name": "read_page", "description": "重新观察页面,返回最新摘要。",
   "input_schema": {"type": "object", "properties": {}}},
  {"name": "done",
   "description": "步骤结束。success=false 时必须给 reason。",
   "input_schema": {"type": "object", "properties": {
       "success": {"type": "boolean"}, "reason": {"type": "string"}},
       "required": ["success"]}},
]
```

### 7.2 系统提示词(全文)

```
你是 seatunnel_agent 项目「数据对比」页面的 UI 测试执行器。
你收到一条测试步骤指令和当前页面摘要,通过调用工具在真实浏览器中完成该步骤。

规则:
1. 只做指令要求的事,不多点、不探索、不修复页面问题;
2. 每次最多调用一个工具,先看摘要再行动;不确定元素状态时先 read_page;
3. 元素名一律使用页面摘要中出现的标签文本;
4. 指令完成后立即调用 done(success=true);
5. 连续两次行动后页面无变化,或找不到目标元素,调用
   done(success=false, reason=具体原因),不要硬试;
6. 不要输出任何解释文字,只调用工具。
```

### 7.3 循环实现(节选,复用项目 LLMClient)

```python
class UITestLLM:
    def __init__(self):
        self.client = LLMClient(load_settings(), tools=UI_TOOLS)
        self.tokens_used = 0

MAX_ROUNDS, TOKEN_BUDGET = 8, 30_000

def run_ai_step(step: Step, dc: DCPage, llm: UITestLLM) -> StepLog:
    t0 = time.time()
    messages = [{"role": "user",
                 "content": f"步骤指令:{step.ai}\n\n当前页面摘要:\n{dc.digest()}"}]
    for round_no in range(MAX_ROUNDS):
        resp = llm.client.chat(_SYSTEM, messages)
        llm.tokens_used += resp.usage.get("input", 0) + resp.usage.get("output", 0)
        if llm.tokens_used > TOKEN_BUDGET:
            return StepLog(step.ai, False, _ms(t0), "token 预算超限")
        if not resp.wants_tool_use:                 # 模型没调工具,视为失败
            return StepLog(step.ai, False, _ms(t0), f"未调用工具: {resp.reply_text[:200]}")
        messages.append(llm.client.append_assistant(resp.raw_content))
        results = []
        for tc in resp.tool_calls:
            if tc.name == "done":
                ok = bool(tc.input.get("success"))
                return StepLog(step.ai, ok, _ms(t0),
                               tc.input.get("reason", f"{round_no+1} 轮完成"))
            out = _exec_tool(tc, dc)                # 映射到 DCPage,异常转文本
            results.append({"type": "tool_result", "tool_use_id": tc.id,
                            "content": out[:2000]})
        messages.append(llm.client.build_tool_result_message(results))
    return StepLog(step.ai, False, _ms(t0), f"超过 {MAX_ROUNDS} 轮未完成")
```

`_exec_tool` 内:每个动作执行后自动附带一次 `dc.digest()` 结果作为 tool_result,
让模型"行动后即观察",省一次 read_page 往返。

### 7.4 judge(judge.py)

单轮、无工具、低温度;输入 = 预期 + 摘要(P1 加截图 base64,Anthropic 走
`{"type":"image"}` 块,OpenAI 走 `image_url`,LLMClient 需小幅扩展支持 content 块)。
输出强制 JSON:`{"verdict":"pass|fail","reason":"..."}`,解析失败重试一次,再失败记 ERROR。

## 8. 环境管理(env.py)

```python
class AppUnderTest:
    """被测应用子进程。绝不使用 7860;端口被占则 +1 续探。"""
    def __init__(self, port=7912):
        self.port = _first_free_port(port)

    def __enter__(self):
        seed_sqlite("config/uitest_demo.db")        # 幂等重建 dc_test_* 十表
        self.proc = subprocess.Popen(
            [sys.executable, "-c", _LAUNCH_SNIPPET % self.port],
            stdout=open(self.log_path, "w"), stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)  # win: 可整树 kill
        _wait_http(f"http://127.0.0.1:{self.port}", timeout_s=40)
        return self

    def __exit__(self, *exc):
        self.proc.terminate()                        # win 下 fallback: taskkill /T /F
        self.proc.wait(timeout=10)
```

`seed_sqlite`:用 Python 直插(非解析 .sql),十张 `dc_test_*` 表、行级数据与
`examples/dc_hive_test_data.sql` 完全一致(单一事实来源:把行数据定义为
`seed_sqlite.py` 里的常量,并加一个单测校验其与 SQL 文件解析结果一致,防两处漂移)。
SQLite 类型映射:STRING→TEXT,DOUBLE→REAL,DECIMAL→REAL(断言值不受影响)。
分区表在 SQLite 中退化为带 `dt` 普通列的表——分区比对功能本就按列 GROUP BY,兼容。

## 9. 报告(report.py)

- `result.json`:`RunResult` 全量序列化(dataclasses.asdict);
- `report.html`:静态单文件,视觉复用 `examples/dc_test_checklist.html` 的
  token/卡片风格;顶部四色统计条(PASS 绿/FAIL 红/ERROR 橙/SKIP 灰)+ 按状态筛选;
  每用例可展开:步骤时间线(动作、定位方式、耗时)、断言明细(期望 vs 实际)、
  失败截图内嵌(base64,报告单文件可直接发群里)、`ai:` 步骤附轮数与 token;
- 终端输出:每用例一行实时进度 + 末尾汇总表(便于 CI 日志阅读)。

## 10. CLI(__main__.py)

```
python -m seatunnel_agent.ui_testing run
    --suite smoke|full|hive|slow    # 按标签,默认 smoke
    --case A5 B3 ...                # 指定用例(优先于 suite)
    --headed                        # 有头浏览器(调试)
    --port 7912                     # 被测应用端口
    --no-llm                        # 跳过 ai:/ai_judge(标 SKIP),纯脚本极速回归
    --keep-app                      # 结束后不杀应用(连续调试)
python -m seatunnel_agent.ui_testing list [--suite full]
```

`--no-llm` 是日常开发的默认姿势:20 条冒烟纯脚本 3 分钟内跑完,零 token。

## 11. pytest 桥接(M3)

```python
# tests/test_ui_smoke.py
@pytest.mark.uitest        # pytest -m uitest 显式开启,默认 deselect
def test_ui_smoke():
    rr = run_suite("smoke", no_llm=True)
    bad = [c for c in rr.cases if c.verdict in ("FAIL", "ERROR")]
    assert not bad, "\n".join(f"{c.case_id}: {c.reason}" for c in bad)
```

## 12. 安全与脱敏

- 报告/日志/LLM 消息三处统一走 `mask()`:`.env` 中 `*_PASSWORD`、`API_KEY`
  等值出现即替换 `***`;页面摘要生成时对 `type=password` 框只输出 `<masked>`;
- LLM 只收页面摘要与截图,不收 `.env`、不收源码;
- 用例 YAML 禁止内联真实凭证(loader 检测 `password:` 字段直接拒载,提示走 .env);
- 种子库固定 `config/uitest_demo.db`,清理动作只 `DROP dc_test_*` 前缀。

## 13. 成本与用量估算

| 项 | 估算 |
|----|------|
| 纯脚本用例 | 0 token,平均 5~8s/例 |
| `ai:` 步骤 | 摘要 ~1.5k tok/轮 × 平均 3 轮 ≈ 6k tok/步 |
| `ai_judge` | ~2k tok/条 |
| 全量套件(55 例,约 15 个 ai 点) | ≈ 120k token/轮,数元人民币级 |

## 14. 对本 Agent 自身的测试

- loader:YAML 缩写展开、非法动作报错、标签过滤 —— 纯单测;
- asserts:各断言对 mock DCPage 的判定与失败文案 —— 纯单测;
- page.py:against 真实应用的最小集成测(启动 7912,textbox/button/dropdown
  三类定位各一条)—— 即冒烟集的 P0-2;
- agent 循环:mock LLMClient 回放固定 tool_calls 序列,验证轮数上限、预算熔断、
  done(false) 路径 —— 纯单测,不花 token。

## 15. 实施顺序(与里程碑对应)

```
M1  models → loader → seed_sqlite → env → page(踩坑集中攻坚) →
    actions/asserts → runner → report → 20 条冒烟 YAML → 连跑 10 轮修 flaky
M2  agent 循环 → judge → LLMClient content 块小扩展(截图) →
    余量用例迁移(≥55) → --no-llm 通道验证
M3  diagnose → Gradio /uitest 页 → pytest 桥接 → 文档 + 演示脚本
```

**第一步落地建议**:先写 `page.py` + 3 条用例(A4/A5/B3)打穿全链路,
再横向铺开——链路通了,剩下的都是填表。
