# 批次结果报告:uitest-react 批次 5a 清理与链路(2026-10-16)

## 批准依据

> 用户经 grilling 评审后确认拆分 "5a/5b",并回复:"批次 5a"。
> 范围来自评审结论:Q3A/Q7A 去 PWA+自毁 SW;Q2B/Q9B 删 Gradio 页+常量上移+提示页;Q1A/Q8B CI 构建链路。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 移除 vite-plugin-pwa;新增自毁 service worker(反注册+清缓存,根治已注册 SW 的浏览器) | frontend/uitest/vite.config.ts, package.json, public/sw.js | 本批次 commit |
| 高 | 删除 Gradio 回退页;共享常量上移到 catalog.py(SUITES/AGENT_ROUTES/AGENT_LABELS/agent_case_ids) | 删 gradio_page.py;新增 catalog.py;api.py 改导入 | 本批次 commit |
| 高 | dist 缺失时 /uitest 返回提示页(含构建命令),hub 其余页面不受影响 | src/seatunnel_agent/hub/ui.py | 本批次 commit |
| 中 | CI:lint.yml 新增 frontend job(npm ci/build/lint/format:check);uitest.yml 冒烟前构建 dist 并把 frontend/uitest/** 纳入触发路径 | .github/workflows/lint.yml, uitest.yml | 本批次 commit |

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 100 source files
pytest -q              -> 2902 passed, 1 skipped, 94 deselected in 116.34s
npm run build          -> ✓ built in 9.24s(dist 仅 assets/index.html/sw.js,无 workbox/manifest)
python scripts/check_workflow.py -> 输出附于本批最终 commit 后(见对话)
```

真浏览器/接口实测(hub 运行于 127.0.0.1:7860):

```
无 dist:GET /uitest        -> 200 提示页 "UI Testing frontend is not built... npm ci && npm run build"
无 dist:GET /api/uitest/meta -> 200(API 不依赖 dist)
有 dist:GET /uitest/        -> 200 <title>UI Testing Agent</title>(React 页)
有 dist:GET /uitest/sw.js   -> 200 自毁 SW 内容
```

## 前后差异

- 前:双实现(React + 277 行 Gradio 回退页),PWA SW 会缓存旧构建;CI 不构建前端,冒烟测的是回退页。
- 后:单实现 + 一页式提示页;SW 自毁清缓存;CI 构建/静态检查前端,冒烟套件跑在 React 页之上。
- 测试:5a 前后全量 pytest 均为 2902 passed, 1 skipped(无回归)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | /uitest 页仍无测试覆盖 | 无相关用例/单测 | 属批次 5b 范围 | 回归只能靠人工 | 批次 5b:api.py 单测 + 1 条浏览器冒烟 |
| 低 | uitest-nightly.yml 未加前端构建步骤 | workflows/uitest-nightly.yml | nightly 只回归各 agent 页,不涉 /uitest 页 | nightly 中被测应用 /uitest 显示提示页 | 若 5b 用例进 nightly 再补 |
| 低 | 启动后数秒 /uitest 404 竞态(沿袭批次 2-4 遗留) | 本批验证时复现一次 | Gradio 6 launch 后挂载 | 启动头几秒 | 可接受 |

## 未执行的步骤

- uitest smoke 套件:未执行 —— 本批次 Python 侧只动了 /uitest 挂载与常量模块,smoke 的 91 条用例均不经过 /uitest 页;以全量 pytest + 双路径真浏览器实测代替。CI 侧 uitest.yml 会在 PR 上自动跑 smoke。
