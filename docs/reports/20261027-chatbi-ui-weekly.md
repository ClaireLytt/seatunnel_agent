# 批次结果报告:UI 露出·周报下载 + PR 草稿更新(2026-10-27,UI 线收官)

## 批准依据

> 用户对"更新 PR 草稿 → 做路线图 5"回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | REST `GET /session/{id}/report/weekly`:会话连接上生成确定性周报骨架 Markdown(零 LLM) | api_metrics.py | 本批 |
| 中 | 健康页「📄 周报」按钮:一键下载 `weekly_<日期>.md`(客户端 blob,无落盘权限问题);i18n 中英 | HealthView.tsx, api.ts, i18n.ts | 本批 |
| — | PR 草稿更新:标题与正文覆盖全部批次(第二波引擎能力/UI 露出/测试 3396→3470 与 21 条浏览器回归),修正 body-file 路径 | docs/PR_DRAFT_uiskill.md | 本批 |

测试:REST 周报并入健康端点测试(markdown 含"经营周报"+gmv,未知会话 404);Playwright 健康页测试追加 expect_download 断言(文件名 weekly_ 前缀)。

## 验证结果

```
python -m pytest tests/test_t2s_connect_api.py -q -> 6 passed
npm run lint/build --workspace text2sql -> 通过(replaceAll 超 TS target,改 split/join 后重建)
python -m pytest -m uitest tests/test_t2s_page.py -q -> 21 passed
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 174 source files
python -m pytest -q          -> 3470 passed, 1 skipped, 246 deselected in 160.01s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- UI:健康页可一键下载确定性周报;UI 露出路线图 1–5 全部完成且有浏览器回归。
- 测试数持平(断言并入既有用例)。

## 未解决问题 / 遗留清单

无。UI 线与引擎线双收官;待办仅剩流程项:PR 创建(草稿已同步)、/metr-finish。

## 未执行的步骤

无。
