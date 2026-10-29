# 批次结果报告:数仓卫生检查 Web UI(/hygiene)(2026-10-29)

## 批准依据

> 上批报告遗留清单声明"Web UI 页…作为独立批次补";用户回复"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | React 工作区 lineage_hygiene(vite base /hygiene/、@shared 组件、双语 i18n),目录+粘贴 SQL 两种入口 | frontend/lineage_hygiene/*, frontend/package.json | 本批 |
| 高 | 平台 manifest(hub 卡:governance 组 order 51、🧹、REST 挂载) | src/.../lineage_hygiene/manifest.py | 本批 |
| 高 | Playwright 页测 3 项(英文 chrome/demo 目录/粘贴 SQL 出 orphan+死列) | tests/test_hygiene_page.py | 本批 |

## 验证结果

```
pytest -m uitest tests/test_hygiene_page.py -q -> 3 passed
pytest tests/test_hub_pages.py -q              -> 16 passed
pytest -q                                      -> 3558 passed, 1 skipped, 253 deselected
ruff check src tests                           -> All checks passed!
mypy                                           -> Success: no issues found in 176 source files
cd frontend/lineage_hygiene && npm run build   -> built in 3.31s
cd frontend/lineage_hygiene && npm run lint    -> (eslint 无输出,通过)
python scripts/check_workflow.py --range origin/main...HEAD ->
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/main...HEAD)
```

浏览器实测(chrome-devtools MCP):/hygiene 渲染正常,demo 目录一键分析输出
"orphan 1 · dead-col 3 · dangling 0";/data hub 列出新卡。

## 前后差异

- 卫生 agent 四表面补齐(UI/CLI/REST/MCP),与套件其余 agent 同构;
  Playwright 页测 31→32 个文件。

## 未解决问题 / 遗留清单

无(上批"UI 页未做"遗留项就此关闭)。

## 未执行的步骤

- issue #10 新候选勾选与编排器路由待用户确认该 agent 定位后进行。
