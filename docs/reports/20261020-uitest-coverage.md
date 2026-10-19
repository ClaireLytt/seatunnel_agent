# 批次结果报告:uitest-coverage(data 工作区按钮级覆盖补全)(2026-10-20)

## 批准依据

> 用户:"/implement-spec"(按 spec `.scratch/uitest-data-agent-coverage/spec.md` 全量实施 5 张票);
> 基底选择:"基于 ui-build-incremental(堆叠)";
> 合并与发布:"跑完把其他分支内容直接本地合进 ui-build-incremental 然后ship上去"、"跑完直接ship"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票01:下载/剪贴板真测(expect_download + clipboard 断言模式) | tests/test_dataskew_page.py、test_sql_review_page.py、test_config_migrate_page.py、test_transpile_page.py | 899bc33 |
| 高 | 票05:9 页非默认方言用例 + sql_review→Transpile 桥/Stats + testgen 滑条 | tests/test_{impact,metricdiff,pii,schemadrift,sqlfmt,testgen,sql_review,lineage,dataskew,transpile}_page.py | 465dc77 |
| 高 | 票04:dataskew 4 面板用例、lineage 方向/剪贴板/路径/Agent 用例;退役 LIN13 | tests/test_dataskew_page.py、test_lineage_page.py、src/.../cases/extended.yaml | 551cd0d |
| 高 | 票03:text2sql 10 用例(聊天控件/五视图/订阅闭环)+ store 隔离 | tests/test_t2s_page.py | 6219932、4cca8b9 |
| 高 | 票02:datacompare 核心/复合动作、8 特性 run、生成卡、报告/模板/趋势/调度、导出 | tests/test_datacompare_page.py | 9fde836 |
| 中 | code-review 修复:helper 去重入 conftest、方言切换共用 helper、labeled_select 替换 nth 定位、桥断言强化、Diff SQL happy path 等 7 项 | tests/conftest.py + 11 个 page test 文件 | af477ed |
| 低 | loader 用例下限 44→43(LIN13 退役的机械跟随) | tests/test_ui_testing.py | 4724e3e |

## 验证结果

逐条命令与结尾输出行(均为真实执行结果):

```
ruff check src tests                               -> All checks passed!
mypy                                               -> Success: no issues found in 113 source files
python -m pytest                                   -> 3241 passed, 1 skipped, 198 deselected, 2 warnings in 130.46s
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                                                   -> PASS 30 · FAIL 0 · ERROR 0 · SKIP 0 · MANUAL 0 · 耗时 110s
                                                   -> 报告: runs/20261020_001836/report.html
票级定向 uitest(修复后终态,ticket02 worktree)      -> 147/147 selected uitest passed(首轮 1 failed 146 passed,修复后重跑该用例 1 passed)
python scripts/check_workflow.py                   -> (见本报告落盘提交后的输出,附在 PR/会话中)
```

真浏览器已验:uitest smoke 报告 `runs/20261020_001836/report.html`;各票 Playwright 定向跑尾行见上。

## 前后差异

- 测试类:
  - data 工作区 15 个 React 页的 Playwright 用例从约 100 条增至 **247+ 条**(新增约 60 测试函数,+~1800 行);全仓库 `expect_download` 从 **0 处 → 14+ 处**(下载按钮由"仅断言可见"变为真下载校验文件名+内容);剪贴板断言 0→5;非默认方言用例 0→10 页。
  - yaml 套件 44→43 用例(LIN13 退役,由 `test_lineage_direction_filter_up_down` 对等取代)。
  - 全量 pytest:批前 3240 passed + 本批触发 1 failed(loader floor)→ 修复后 **3241 passed, 0 failed**。
- 控件→测试函数对照清单(本批补齐的缺口):

| 页面 | 补齐控件 | 测试函数(tests/test_*_page.py) |
| --- | --- | --- |
| data_skew | 下载报告/优化 SQL、Copy SQL、llm 模式降级、split-key 上传/检查/下载、Runtime 拉取+上传、预设 load、采样切换、方言切换 | test_dataskew_download_report / _download_optimized_sql / _copy_sql_clipboard / _llm_mode_no_key_banner / _splitkey_upload_check_download / _runtime_panel / _preset_load_and_sample_verify / _dialect_switch_hive |
| sql_review | Download Report 真下载、→Transpile 桥(弹窗页预填断言)、Stats Refresh、方言切换 | test_sql_review_download_report / _page_transpile_bridge / _page_stats_refresh / _dialect_switch_mysql |
| config_migrate | 复制配置到剪贴板 | test_config_migrate_copy_conf_clipboard |
| sql_transpile | Copy SQL、显式源方言(非 auto) | test_transpile_copy_sql_clipboard / _source_dialect_hive |
| data_lineage | 方向过滤(双向)、Copy mermaid、路径分析、Agent 真实提问降级、方言切换 | test_lineage_direction_filter_up_down / _copy_mermaid_clipboard / _path_analysis / _agent_real_question_no_key / _dialect_switch_spark |
| data_comparison | count/sample/aggregate/profile/batch-count/batch-full、8 特性 run、生成卡 4 按钮+sync 下载、报告闭环+趋势、模板删除+批量、调度启停、Preset B+环境对比、CSV/Excel/独立报告、Diff SQL happy path | test_datacompare_count_sample_aggregate_cards / _profile_and_batch_actions / _feature_accordion_runs / _generation_card_buttons / _reports_cycle_and_trends / _templates_delete_and_batch_run / _schedule_start_stop / _preset_save_b_and_env_compare / _export_downloads_and_standalone_report / _generate_diff_sql_happy_path |
| text2sql | Enter 发送、Stop、上一页、CSV/PNG 导出、👍/👎、select-all/reload、History 四控件、Favorites 改名/删除/刷新、Metrics 展开/use、Boards 四控件、Subscriptions 闭环+⟳、模板 chip | test_t2s_chat_enter_stop_pager / _csv_png_export_and_feedback / _schema_select_all_reload / _history_controls / _favorites_rename_delete_refresh / _metrics_expand_use / _boards_lifecycle / _subscriptions_lifecycle / _template_chip_prefill(命名以文件为准) |
| impact/metricdiff/pii/schemadrift/sqlfmt/testgen | 非默认方言切换(+testgen 滑条行数生效) | test_<page>_dialect_switch_spark|mysql / test_testgen_rows_slider_effective |

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | api.py 与 generation.py 各持一个 ConnectionPresetsStore 实例指向同一文件 | 票02 代理报告(生产同文件,非 bug) | 模块各自实例化 | 目前无;重构时易踩 | 后续合并为单例,暂不动(精准修改原则) |
| 低 | t2s FakeAgent chat_page_url 的 import-time binding 坑(api.py 按值绑定 build_agent) | 票03 报告;测试层已双 patch 修复 | import 期函数引用绑定 | 新 fixture 复用时可能再踩 | 再遇一次按 §6 记入 docs/pitfalls.md |
| 低 | datacompare 报告文件名秒级时间戳,测试用 wait_for_timeout(1100) 规避 | tests/test_datacompare_page.py(已留注释) | 服务端命名无注入点 | 极低概率慢机器抖动 | 如出现 flake,给 save_report 加可注入命名 seam |
| 低 | frontend data_skew/data_lineage 若干 select 无 id/aria,测试用 label 锚定 | 票修复代理报告(labeled_select) | 前端未加稳定测试钩子 | 改 label 文案会牵动测试 | 下次前端批次顺带补 data-testid |

## 未执行的步骤

- LLM 真调用路径的端到端测试:spec 明确排除(只测无 key 降级)。
- ai / devops 工作区与 3 个 Gradio 页(dagcheck/loginspect/mcp)的用例扩充:spec Out of Scope。
- `python scripts/check_workflow.py` 在本报告提交之后执行(机械核对要求报告先落盘),输出附于会话与 PR。
