# 批次结果报告:data 工作区 manifest 迁移 #52-#55(2026-10-16)

## 批准依据

> 架构评审候选①经 grilling 六问全部按推荐确认("yes"),拆票方案经 /implement 批准执行;spec 为 issue #51,子票 #52-#55。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | #52 registry 加 `group`/`card` 字段;card_html 消费 color/logo 渲染彩色块+Enter 行(ai/devops 卡片随之升级) | hub/registry.py, tests/test_registry.py | 1ee25e1 |
| 高 | #53 17 个包 21 条路由的 manifest(data_lineage/text2sql 一包多 manifest);#54 /data 改 manifest 渲染,删手写卡片 HTML+正则+21 块硬编码路由(原子合并,防路由双注册) | agents/data/*/manifest.py ×17, hub/pages.py, hub/ui.py | d80cab3 |
| 高 | #55 13 个 data router 改走 manifest api=,删 launch_app 手工元组(--api + X-API-Key 语义不变) | agents/data/*/manifest.py, hub/ui.py | 850b65b |

## 验证结果

```
RED 证据(TDD):
  TestDataCoverage 先行       -> 2 failed(manifest 不存在)
  TestDataApiRouters 先行     -> 1 failed(api= 未声明)
GREEN / 全量:
  ruff check src tests        -> All checks passed!
  mypy                        -> Success: no issues found in 103 source files
  pytest -q                   -> 2914 passed, 1 skipped, 95 deselected in 128.13s
  uitest smoke --no-llm       -> PASS 91 · FAIL 0 · ERROR 0 · SKIP 2 · MANUAL 4 · 耗时 662s
                                 报告: runs/20261016_210705/report.html
  --api 语义实测              -> 5 组样本端点(sql_review/text2sql/sqlfmt/skew/lineage)/health 全 200
```

截图前后对比(before 由 c98fe93 的临时 worktree 实跑截取):
- /data:hub_data_before.png → hub_data_manifest.png(三分组 16 卡、№ 33 agents、筛选行,结构等价)
- /ai:hub_ai_before.png → hub_ai_manifest.png(卡片升级富样式)
- /devops:hub_devops_before.png → hub_devops_manifest.png(同上)
- landing:hub_landing_manifest.png

python scripts/check_workflow.py 输出附于本报告 commit 后(见对话)。

## 前后差异

- 前:新增 data agent 需改 hub/ui.py + hub/pages.py 共 3+ 处;pages.py 用正则重解析自己手写的 400 行 HTML;launch_app 维护 13-router 元组。
- 后:新增 agent = 放一个带 manifest 的包;hub 剩 5 个 app.route(landing/3 workspace/settings);手工清单 ~300 行删除。
- 测试:2909 → 2914 passed(+5:coverage/group/card/api 契约测试);smoke 91 条全绿不变。

## 代码评审结论(双轴,两个并行子 agent)

见对话中的汇总;要点已按处置记录于下方遗留清单。

## 范围偏差说明(Spec 轴评审指出,已核)

- `card` 字段与 `MANIFESTS` 复数支持:#51 只写了 `group` 字段 —— 这两项是迁移 21 条路由的必要机制(text2sql 辅助页无卡、data_lineage 一包两页),属实现决策而非功能蔓延;已在本报告记录。
- landing 的 loginspect/mcp 卡片改由 `card_html(manifest)` 生成:与 #51 "landing 不迁移"字面不符,但文案逐字段相同、渲染等价;备选是在字面量里再留两张手写卡(回到重复)。保留现状。
- `_card_blocks()` 正则仍在:只服务 uitest/settings 两张无 manifest 的卡,见遗留清单。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 新 manifest 文件重新编码了既有蓝紫色号(#8b5cf6/#7c3aed/#6366f1/#9333ea/#4f46e5) | agents/data/*/manifest.py | 迁移按 grilling Q1A"视觉零变化"决议逐字段搬运旧卡片色;色板本身先于 CLAUDE.md §2 存在 | 渲染结果与迁移前逐像素一致,无新增蓝紫元素 | 如需换色板,另立 UI 批次全局调色,勿混入本次机械迁移 |
| 低 | sidebar_resize 路由集合硬编码回 hub | hub/ui.py manifest 循环 | 3 页专属行为,manifest 加字段属过度设计(§3 保持简单) | 新宽页 agent 需改 hub 一处 | 第 4 个需要者出现时再升为 manifest 字段 |
| 低 | `card=False` 的 manifest 在 landing 仍渲染卡片,语义易误读 | hub/pages.py landing eng_cards | card 字段含义是"不在 workspace 页出卡" | 读者需看注释 | 后续改名(如 workspace_card)可另批 |
| 低 | `_card_blocks()` 正则只服务 2 张字面量卡(uitest/settings) | hub/pages.py | uitest 是 React 页、settings 是 hub 页,无 manifest | 少量冗余机制 | 待 uitest/settings 入册后删除正则 |

## 未执行的步骤

- 无 dist 场景 / nightly 流水线复测:未执行 —— 本批未触及 uitest 挂载逻辑。
