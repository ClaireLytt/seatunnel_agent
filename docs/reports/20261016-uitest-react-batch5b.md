# 批次结果报告:uitest-react 批次 5b 历史列表与测试(TDD)(2026-10-16)

## 批准依据

> 用户:"批次 5b 用tdd流程开发"。范围来自 grilling 评审:Q10B 历史运行列表(富版,无删除按钮)、Q5C 双层测试、Q11A 浏览器冒烟 monkeypatch runner。

## 已完成(每条按 red → green 循环)

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 新端点 `GET /api/uitest/runs`:列 runs/<ts>/,读 result.json 聚合计数,损坏目录跳过(先红后绿) | src/seatunnel_agent/agents/devops/ui_testing/api.py | 本批次 commit |
| 高 | API 单测 7 条:runs / meta / case 保存与 422 / report 404+422 / SSE 协议(monkeypatch run_suite)/ 未知套件 422 | tests/test_uitest_api.py | 本批次 commit |
| 高 | 浏览器冒烟(uitest mark):进程内 uvicorn + dist,断言标题/下拉填充/历史区/点 Run 后 SSE 进度与计数(先红后绿) | tests/test_uitest_page.py | 本批次 commit |
| 中 | 前端历史运行区:表格展示 run_id/suite/着色计数/耗时,查看(复用报告 iframe)+ 下载 | frontend/uitest/src/App.tsx, api.ts, i18n.ts | 本批次 commit |

## 验证结果

```
RED 证据:
  /runs 测试先行          -> 1 failed (AssertionError, 404)
  浏览器冒烟先行           -> 1 failed (.st-history 不存在)
GREEN:
  pytest tests/test_uitest_api.py -q      -> 7 passed
  pytest -m uitest tests/test_uitest_page.py -q -> 1 passed
全量:
  ruff check src tests   -> All checks passed!
  mypy                   -> Success: no issues found in 100 source files
  pytest -q              -> 2909 passed, 1 skipped, 95 deselected in 114.31s
  npm run build / lint / format:check -> 全过
python scripts/check_workflow.py -> 输出附于本批最终 commit 后(见对话)
```

## 前后差异

- 测试:默认套件 2902 → **2909 passed**(+7 条 API 测试);uitest mark 新增 1 条 React 页冒烟(此前该页零覆盖)。
- UI:新增 "Past runs / 历史运行" 区。截图:docs/reports/shots/uitest_history.png(对比 5a 前的 uitest_light_blackgrid.png,新增历史表格,19 条真实运行、FAIL/ERROR 标红、查看/下载可用)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 历史行 suite 列在指定用例运行时显示用例 id 串(如 "DEVO1,SEC1,…") | 截图第 8 行;result.json 的 suite 字段由 runner 如此写入 | runner 复用 suite 字段记录 case_ids | 仅展示语义略歧义 | 如介意可在 runner 写入处分字段,属 runner 改动需另批 |
| 低 | 浏览器冒烟在 CI 需 dist(已由 uitest.yml 构建步骤保证),本地未构建时 skip | tests/test_uitest_page.py 的 pytest.skip | 设计取舍 | 本地未构建时该用例不跑 | 可接受 |

## 未执行的步骤

- uitest smoke 全套件:未执行 —— 本批 Python 改动仅 api.py 新增只读端点与测试文件,不触及 smoke 用例路径;以全量 pytest + 新浏览器冒烟代替,CI 的 uitest.yml 会在 PR 上跑全套 smoke。
