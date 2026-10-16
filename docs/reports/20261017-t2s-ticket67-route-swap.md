# 批次结果报告:text2sql 票 #67 路由切换(2026-10-17)

## 批准依据

> 用户 /implement 驱动 frontier;UI 放行以用户后续 /implement 指令作实(模式同 #65/#66,已在对话声明)。

## 已完成(TDD)

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | registry 加 `external` 字段(出卡不注册 Gradio 路由);text2sql 主 manifest 转 external,新增 text2sql_legacy manifest(card=False) | hub/registry.py, agents/data/text2sql/manifest.py | 本批次 commit |
| 高 | React 正式接管 `/text2sql`(vite base 切换、静态挂载换路径、未构建提示页含 legacy 链接);旧 Gradio 页挪 `/text2sql-legacy`;sidebar_resize 名单跟随 | hub/ui.py, frontend/text2sql/vite.config.ts | 本批次 commit |
| 高 | React 侧栏新增"暂在旧版页"功能链接组(模板/指标/收藏/反馈/订阅/看板 → legacy) | frontend/text2sql/src/App.tsx, i18n.ts | 本批次 commit |
| 中 | 9 条 `page: /text2sql` 用例改指 `/text2sql-legacy`(待 #75 适配 React DOM);页面冒烟路径随切换 | cases/*.yaml, tests/test_t2s_page.py | 本批次 commit |

registry 测试先红(2 failed)后绿;external 跳过逻辑由既有 smoke 全套验证。

## 验证结果

```
RED:  TestExternalManifest -> 2 failed(字段不存在)
GREEN: tests/test_registry.py 13 passed
全量: pytest -q -> 2929 passed, 1 skipped(+1);mypy Success;ruff All checks passed!
前端: npm build / lint 全过;页面冒烟 2 passed(已指向 /text2sql)
smoke 全套(票内硬性验收): PASS 91 · FAIL 0 · ERROR 0 · SKIP 2 · MANUAL 4 · 655s
      报告: runs/20261017_015712/report.html
踩坑: heredoc 反斜杠第三次命中(hint 页字符串断裂),Edit 修复 —— 规避法已在 pitfalls,本次起 heredoc 内不再写含反斜杠的源码
```

## 前后差异

- 前:/text2sql = Gradio 页;React 版躲在 /text2sql-next。
- 后:/text2sql = React(连接+流式问答+图表导出);旧页完整保留于 /text2sql-legacy,未迁功能从新页一键可达;hub 卡片不变。
- 测试:2928 → 2929 passed;smoke 91 条全绿不变。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 9 条 text2sql 用例跑在 legacy 页,React 主页仅 2 条进程内冒烟覆盖 | cases/*.yaml page 字段 | 适配属 #75 | 主页回归弱于迁移前 | #75 适配全部用例 |
| 低 | /text2sql-next 旧书签失效 | 挂载已移除 | 开发路由本就临时 | 无 | 无需处理 |

## 未执行的步骤

- 无。
