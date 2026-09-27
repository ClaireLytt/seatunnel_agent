# UI 测试 Agent 使用指南

> 设计与 PRD 见 [ui_test_agent_design.md](ui_test_agent_design.md)。
> 用例库与 `examples/dc_test_checklist.html` 的 75 项人工清单同源同编号;
> SR 组用例额外覆盖 SQL Review 页(`/sqlreview`,纯静态审查路径);
> LIN 组覆盖数据血缘页(`/lineage`,演示数据 `examples/lineage_demo`);
> T2S/HIS/FAV/SCH 组覆盖 Text2SQL 侧栏与历史/收藏/Schema 浏览器辅助页;
> TRP 组覆盖 SQL 方言翻译页(`/transpile`,演示数据 `examples/transpile_demo`);
> IMP 组覆盖变更影响分析页(`/impact`,目录/粘贴/上下文三种模式,演示数据 `examples/impact_demo`);
> MIG 组覆盖配置迁移页(`/migrate`,演示数据 `examples/migrate_demo`);
> SET 组覆盖设置页(`/settings`,LLM API 界面配置;被测应用的设置文件被
> 隔离到本轮 `runs/<ts>/`,不会触碰开发者真实配置);
> SCR 组回归全部七个页面的滚动容器(500px 小窗验证内容可滚到底,
> 并固化"哪个容器负责滚动"的契约)。

## 快速开始

```bash
# 冒烟回归(纯脚本,零 token,约 3 分钟)
python -m seatunnel_agent.ui_testing run --suite smoke --no-llm

# 全量回归(含 LLM 模糊断言,需要 .env 配置 API_KEY)
python -m seatunnel_agent.ui_testing run --suite full

# 只跑指定用例 / 有头调试
python -m seatunnel_agent.ui_testing run --case A5 B3 --headed

# 列出用例
python -m seatunnel_agent.ui_testing list [--suite smoke]
```

运行结束输出 `runs/<时间戳>/`:

| 文件 | 内容 |
|------|------|
| `report.html` | 单文件报告:四色统计条、按状态筛选、逐用例步骤/断言明细、失败截图内嵌 |
| `result.json` | 机器可读全量结果(已脱敏) |
| `shots/` | 截图 |
| `app_under_test.log` | 被测应用 stdout/stderr |

## 运行机制

- Runner 自动以子进程在 **专用端口 7912**(被占则 +1 续探,**绝不碰 7860**)
  启动应用;结束后整树 kill(Windows 走 `taskkill /T /F`)。
- 每轮运行前把十张 `dc_test_*` 表种子进 `config/uitest_demo.db`
  (数据与 `examples/dc_hive_test_data.sql` 逐行一致,单测
  `test_rows_match_hive_sql_file` 保证两处不漂移)。
- 每条用例从新页面加载开始(隔离),默认切中文界面(`lang: en` 可保持英文)。
- 结果四态 + 人工:`PASS` / `FAIL`(断言不过)/ `ERROR`(执行异常)/
  `SKIP`(标签不满足)/ `MANUAL`(标注人工)。
- `--base-url http://127.0.0.1:7912` 可复用已启动的应用(配合 `--keep-app`
  连续调试,免每轮冷启动)。

## 界面上按 Agent 定向测试

`/uitest` 页新增「按 Agent 测」下拉:选 数据对比 / SQL Review / 数据血缘 /
Text2SQL 与辅助页 / SQL 方言翻译 / 变更影响分析 / 配置迁移 / 设置,
点运行即测该 Agent 的全部自动化用例(优先于套件选择;
「指定用例」填了 id 时又优先于它)。

## 界面上零代码添加用例

打开 `/uitest` 页底部「添加用例」手风琴,粘贴一段用例 YAML → 点「校验并保存」。
校验通过后写入 `config/uitest_cases/`(包外,升级不丢;id 与内置用例查重),
随后在「指定用例」里填它的 id 即可运行。配合 `ai:` 步骤 + `ai_judge`,
一条用例可以完全用中文写,无需任何选择器。

## 写用例

用例在 `src/seatunnel_agent/ui_testing/cases/*.yaml`,中文即可,不写 Python:

```yaml
- id: C3                       # 与人工清单编号一致
  title: 行数对比呈现 10 vs 9 差异
  tags: [smoke, sqlite]        # 必含 sqlite 或 hive 之一
  setup:
    - use: select_orders       # 引用 _fixtures.yaml 里的共享前置
  steps:
    - click: 行数对比           # 缩写 = {action: click, args: {target: 行数对比}}
    - wait_result: {}          # 等结果区渲染稳定
    - ai: 打开 B 侧选择表下拉框,输入 user,确认只显示 user 表   # LLM 兜底步骤
  expect:
    - text_contains: {in: 结果区, text: "10"}
    - status_ok: {side: A}
    - ai_judge: 结果卡片明确标记行数不一致(红色/未通过语义)     # LLM 模糊断言
```

动作全集:`goto / click / fill / clear / press / select_ds / select /
dropdown_type / check / slide（滑条取值）/ open_accordion / wait_status_ok / wait_status_error /
wait_result / wait(须写 note) / screenshot / set_language /
download(捕获下载按钮产出的文件)/ popup_click(捕获 window.open 新窗口文本)/
drag_sidebar(拖拽原生 resize 手柄)`。

断言全集:`text_contains / text_not_contains / value_is / options_are /
scrollable(压缩视口验证页面滚动容器)/
options_count / status_ok / status_error / visible / hidden / checked /
download_ok(扩展名/大小/魔数/内容)/ popup_contains / sidebar_width /
ai_judge`。`in:` 可取 `状态` / `结果区` / `页面` / 任意输入框标签。

标签:`smoke`(冒烟)、`full`(全量)、`hive`(需真实 Hive,连不上整组 SKIP)、
`sqlite`(内置演示库)、`slow`(>1min,默认不进 smoke/full)、`manual`(不自动化)。

## LLM 用量与安全

- LLM 只出现在三个窄口:`ai:` 步骤执行、`ai_judge` 断言、失败归因;
  主干全部确定性。`--no-llm` 跳过全部 LLM 用例,零 token。
- 单个 `ai:` 步骤硬顶 8 轮工具调用 / 30k token,超限判 ERROR。
- 报告、日志、LLM 消息统一脱敏(`.env` 中 `*_PASSWORD` / `*API_KEY*` /
  `*SECRET*` / `*TOKEN*` 的值替换为 `***`);密码框在页面摘要中输出 `<masked>`;
  用例 YAML 内联密码会被 loader 直接拒载。
- 复用项目 `LLMClient`(Anthropic/OpenAI 双通道,配置走 `.env` 的 LLM_*)。

## 稳定性与诊断

```bash
python -m seatunnel_agent.ui_testing run --case B3 --repeat 10   # 压 flaky:逐轮比对 verdict,不一致标 FLAKY
python -m seatunnel_agent.ui_testing compare                     # 对比最近两轮:回归/恢复/变慢
python -m seatunnel_agent.ui_testing compare 20260924_1 20260925_2
```

- 报告顶部自动显示「较上轮变化」(同套件的上一轮,verdict 变化 + 明显变慢);
- `ai_judge` 默认附带**页面截图**(多模态,视觉类预期可判);模型不支持视觉时
  自动降级纯文本并在本轮内记住,`UITEST_JUDGE_VISION=0` 可关;
- 定位失败(元素 not found)时自动给出**LABELS 修正建议**
  (LLM 对照页面摘要猜实际标签,写进步骤明细);
- 任何 FAIL/ERROR 自动附 LLM 归因(前端/后端/用例过期/环境),`--no-llm` 时跳过。

## CI 集成

`.github/workflows/uitest.yml`:PR 触发 headless 冒烟(`--no-llm`,零 token,
约 4 分钟),FAIL/ERROR 挡合并,失败时 `runs/` 报告自动上传为 artifact。

## 人工清单覆盖对照

```bash
python -m seatunnel_agent.ui_testing list --coverage
```

输出 75 项人工清单的逐项状态(已自动化/框架内置/人工用例/未覆盖),报告
`report.html` 底部同款可视化(按编号色块,悬停看标题)。

## 自检工具

```bash
python scripts/uitest_inject_bugs.py     # 注入三类 bug(前端接线/后端崩溃/i18n 漂移),验证套件能全部抓到
python scripts/uitest_flaky_check.py 10  # 连续 N 轮冒烟,验证零 flaky(逐轮 verdict 必须完全一致)
```

## pytest 桥接

```bash
pytest -m uitest tests/test_ui_smoke.py                    # 整包 smoke,单节点
pytest -m uitest tests/test_ui_cases.py                    # 逐用例节点(推荐)
UITEST_SUITE=full pytest -m uitest tests/test_ui_cases.py  # 全量
pytest -m uitest tests/test_ui_cases.py -k SCR --lf        # pytest 过滤/重跑失败
pytest -m uitest tests/test_ui_cases.py -n 4 --dist loadgroup  # xdist 并行:
#   每个 worker 独立端口起独立 app;SET6~SET8 共享档案生命周期,
#   已打 xdist_group,loadgroup 会把它们按序留在同一 worker
```

## flaky 趋势

每轮运行自动追加 `runs/history.jsonl`(run 目录会被裁剪,history 长存);
nightly workflow 用 actions/cache 跨夜累积:

```bash
python -m seatunnel_agent.ui_testing trend --last 30   # 近 30 轮 verdict 稳定性
```

## 定位不稳时改哪里

全项目只有 `page.py` 允许出现选择器。Gradio 升级改 DOM,只改这一个文件:
文本框 = `label:has(span) textarea`,下拉 = `input[aria-label=...]` +
`ul[role=listbox] li`,状态框 = `.st-sidebar-status`,结果区 =
`.st-main .st-schema-card`。中英文案对照集中在 `page.py::LABELS`。
