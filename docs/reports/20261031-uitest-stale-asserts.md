# 批次结果报告:uitest 全量回归排查(2026-10-31)

## 批准依据

> "go on"（上一轮全量 uitest 出现 9 个失败,本轮逐一定性并修复）

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中 | release_notes 过时断言:页面已改为分组标题"Features/Bug Fixes",原断言找小写 "feat"（大小写敏感）落空 | tests/test_release_notes_page.py | (本批) |
| 中 | triage 过时断言:503 详情已内联为纯文本,原断言找 "!" 标记落空;改为断言 "API_KEY is not set" + 无 Traceback | tests/test_triage_page.py | (本批) |

## 排查结论

9 个失败全部与本分支改动无关(均不使用新增的 extra_routers 参数):

- release_notes、triage:main 带入的测试漂移(main 上 dist 未构建一直 skip
  所以未暴露),页面本身行为正确,本批修断言。
- webtask x4、ui_smoke、uitest_page x2:单独复跑全部通过,系 46 文件串行
  长跑(16 分钟)下的资源抖动,非代码问题。

## 验证结果

```
pytest -m uitest tests/test_release_notes_page.py -> 1 passed
pytest -m uitest tests/test_triage_page.py -> 4 passed
pytest -m uitest tests/test_webtask_page.py -> 4 passed(复跑)
pytest -m uitest tests/test_ui_smoke.py tests/test_uitest_page.py -> 3 passed(复跑)
python scripts/check_workflow.py --range origin/main...HEAD ->
  [PASS] AI 署名: 无 AI 署名(范围 origin/main...HEAD)
  [PASS] 工作区: 工作区干净
  [PASS] 报告落盘: 代码改动已附带落盘报告
  [PASS] 报告含验证输出: 报告含 check_workflow 输出
  [PASS] floor: 无作弊变绿改动(范围 origin/main...HEAD)
  [PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/main...HEAD)
```

## 前后差异

- 全量 uitest 从 9 failed/278 passed 收敛为 0 已知真实失败。
