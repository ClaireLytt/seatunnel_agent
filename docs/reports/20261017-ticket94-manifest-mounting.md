# 批次结果报告:票 #94 manifest 驱动的 React 挂载(2026-10-17)

## 批准依据

> 架构评审Ⅱ候选①(用户查看报告后以 /to-spec、/to-tickets、/implement 顺序驱动);spec #93。

## 已完成(TDD)

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | registry:`legacy` 字段 + `frontend_dist()` 约定(frontend/<name>/dist);约定单测先红后绿 | hub/registry.py, tests/test_registry.py | 本批次 commit |
| 高 | launcher 两份手写挂载块 → 一个 external-manifest 循环(StaticFiles / 模板化提示页含构建命令与 legacy 链接) | hub/ui.py | 本批次 commit |
| 中 | uitest 新增 card=False 的 external manifest;FRONTEND_DIST 改为 registry 约定的薄别名(供既有测试导入) | agents/devops/ui_testing/manifest.py, api.py | 本批次 commit |

## 验证结果

```
RED:  TestExternalMounting -> 1 failed(frontend_dist 不存在)
GREEN: registry/hub/uitest-api 37 passed
双路径实测: 无 dist -> 提示页(含 npm run build --workspace text2sql 与 legacy 链接)
            有 dist -> /text2sql React、/uitest React、/text2sql-legacy 200
全量: pytest -q -> 2930 passed, 1 skipped(+1);mypy Success;ruff All checks passed!
踩坑: heredoc 反斜杠第四次命中(提示页 f-string),ast.parse 预检拦下 —— 新规:heredoc 写完含字符串源码必跑 ast.parse
```

## 前后差异

- 前:每个 React app 一份 ~20 行挂载块(已 2 份,计划 6 份),dist 路径两种放法。
- 后:launcher 一个循环;新 app 上线 = 写 external manifest 一处;#85/#80/#88/#91 各省一段 hub 手术。
- 测试:2929 → 2930 passed。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | FRONTEND_DIST 薄别名仍存于 uitest api.py | api.py | 两个测试文件在导入 | 一个过渡符号 | #85 顺路把测试改为 registry 导入后删除 |
| 低 | smoke 全套未在本票内重跑 | — | 路由行为与 #67 验收时完全一致(同一循环产物);全量 pytest+双路径实测已覆盖 | CI 会跑 | PR 上 uitest.yml 兜底 |

## 未执行的步骤

- smoke 全套件:未执行(理由见上表,如实标记)。
