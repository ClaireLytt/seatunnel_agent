# 批次结果报告:dagcheck-react(DAG Health Check 页 React 迁移)(2026-10-20)

## 批准依据

> 用户:"/grill-me 按照重构的ui agent界面把DAG Health Check的界面重构,就在现在的分支开发不允许切换新分支";
> 设计树 Q1-Q6 全部 "yes"(先合并 #125、完整切换、DAG1-5 退役、功能 1:1、同款流程、方言 7 项);
> 实施批准:"/implement-spec"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票01:React workspace(form→report 形态,双语,@shared 复用)、manifest external 切换、api= 清空改 hub 挂载、Gradio ui.py 退役、前后截图 | frontend/dag_check/、agents/data/dag_check/(manifest/api)、hub/ui.py、ui_testing/page.py、tests/test_registry.py、tests/test_dag_check.py | f77feca |
| 高 | 票02:Playwright 页测试(DAG1-5 对等+smoke+方言+空输入)、i18n parity 测试、dagcheck.yaml 退役、floor 43→38 | tests/test_dagcheck_page.py、tests/test_dagcheck_i18n.py、cases/dagcheck.yaml(删)、tests/test_ui_testing.py | e46ce3f |
| 中 | review 修复:SeaTunnel 目录控件覆盖、方言请求载荷断言、空输入零请求断言、403 白名单 UI 本地化(request_failed) | tests/test_dagcheck_page.py、frontend/dag_check/src(App.tsx/i18n.ts) | 8931162 |

## 验证结果

```
ruff check src tests                               -> All checks passed!
mypy                                               -> Success: no issues found in 112 source files
python -m pytest                                   -> 3249 passed, 1 skipped, 206 deselected, 2 warnings in 124.89s
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                                                   -> PASS 28 · FAIL 0 · ERROR 0 · SKIP 0 · MANUAL 0 · 耗时 102s
                                                   -> 报告: runs/20261020_012824/report.html
pytest -m uitest -k dagcheck                       -> 10 passed, 3446 deselected (修复后终态)
pytest -k "dag_check or dagcheck" -m "not uitest"  -> 32 passed
pytest tests/test_dagcheck_i18n.py -q              -> 7 passed
python scripts/check_workflow.py                   -> (本报告提交后执行,输出附会话)
```

真浏览器已验:dagcheck Playwright 10 用例 + smoke 报告 `runs/20261020_012824/report.html`。

## 前后差异

- UI 类(截图 docs/reports/shots/):
  - 前(Gradio):dagcheck-gradio-before-en-dark.png / dagcheck-gradio-before-zh-light.png / dagcheck-gradio-before-zh-report.png
  - 后(React):dagcheck-react-en-dark.png / dagcheck-react-zh-report.png(报告含 依赖成环/执行分批/关键路径,功能 1:1)
- 测试类:
  - yaml 套件 43→38 用例(DAG1-5 退役);dagcheck Playwright 用例 0→10;i18n parity 0→7;dag_check 非 uitest 25→32
  - smoke 30→28 PASS(DAG1/DAG2 两条 smoke 床位随退役移除,无失败)
  - 全量 pytest:3241→3249 passed,0 failed
- data 工作区 Gradio 余量:3 页 → **2 页**(loginspect、mcp)

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | api.py 错误契约由 zh-only 字符串改为结构化 bad_dir/check_failed,与 spec"API 已有 tests 不动"一行冲突(已评审判定为 UI 必需:浏览器无法 stat 文件系统、旧串无法本地化) | tests/test_dag_check.py 对应断言已更新;Spec 轴报告 | React 客户端需要可本地化的错误 | 未发现其他消费方;对外行为更规范 | 接受;后续消费方按结构化 detail 解析 |
| 低 | in-process uvicorn fixture 在 tests/*.py 已有 ~35 份拷贝(本批新增第 35 份) | Standards 轴报告 | 历史模式 | 维护成本 | 后续专批收敛进 conftest |
| 低 | bad_dir 白名单三件套散于 ~8 个 agent 的 api.py | Standards 轴报告 | 逐页复制 | 漂移风险 | 后续抽 require_dir_structured() 公共函数 |
| 低 | DIALECTS 列表前端 i18n.ts 与各页重复、无后端单一来源 | Standards 轴报告 | 既有模式 | 由 parity 测试钉住,漂移可测出 | 后续统一到共享常量 |
| 低 | DAG1 旧 yaml 的 result_in_view 滚动断言无 Playwright 对等(用 visible 近似) | Spec 轴报告 | 滚动位置非关键行为 | 极低 | 不处理 |

## 未执行的步骤

- loginspect、mcp 两页迁移:spec Out of Scope。
- `python scripts/check_workflow.py` 于本报告提交后执行(机械核对要求报告先落盘),输出附会话与 PR。
- 推送/PR 更新:待用户指示(ship)。
