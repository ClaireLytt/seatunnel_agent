# 批次结果报告:uitest-react 批次 2-4 后端 API + 功能页 + 验证(2026-10-16)

## 批准依据

> 用户:"1234顺序开发"(批准批次 1-4 按顺序执行)。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 新增 REST/SSE 后端:meta / run(SSE 流式进度)/ report 内嵌与下载 / case 校验保存 | src/seatunnel_agent/agents/devops/ui_testing/api.py | 6b0e9a7 |
| 高 | /uitest 挂载 React 静态页(dist 缺失时回退 Gradio 页);uitest router 随 UI 无条件挂载 | src/seatunnel_agent/hub/ui.py | 6b0e9a7 |
| 高 | React 功能页:运行面板、SSE 进度、Recharts 结果图、报告 iframe + 下载、零代码 YAML 编辑器、中英文随 st-lang cookie | frontend/uitest/src/ (App.tsx, api.ts, i18n.ts, components/) | 8455aa5 |
| 中 | Aceternity "Card Spotlight" 组件移植并换成 landing 工程纸配色(无蓝紫渐变) | frontend/uitest/src/components/ui/spotlight-card.tsx | 8455aa5 |

## 验证结果

```
npm run build            -> ✓ built in 9.30s (PWA precache 5 entries)
npm run lint             -> 无输出(0 错误)
npm run format:check     -> All matched files use Prettier code style!
ruff check src tests     -> All checks passed!
mypy                     -> Success: no issues found in 100 source files
pytest -q                -> 2902 passed, 1 skipped, 94 deselected, 2 warnings in 121.38s
python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm
                         -> PASS 91 · FAIL 0 · ERROR 0 · SKIP 2 · MANUAL 4 · 耗时 682s
                            报告: runs/20261016_124929/report.html
```

真浏览器/接口实测(hub 运行于 127.0.0.1:7860):

```
GET  /uitest/                      -> 200(React index.html)
GET  /api/uitest/meta              -> 200 {"suites":["smoke",...],"agents":[...]}
POST /api/uitest/run (X1)          -> SSE: progress → done {"PASS":1,...,run_id:20261016_124824}
GET  /api/uitest/report/<id>       -> 200
GET  /api/uitest/report/<id>/download -> content-disposition: attachment
POST /api/uitest/case (非法 YAML)  -> 422
```

截图(Playwright,亮/暗):docs/reports/shots/uitest_light.png、docs/reports/shots/uitest_dark.png。

python scripts/check_workflow.py 输出附于本批最终 commit 后(见对话)。

## 前后差异

- 前:/uitest 为 Gradio 页面(gradio_page.py 渲染)。后:/uitest 为 React 18 + TS + Vite + Tailwind + Motion + Recharts + react-i18next + PWA 页面,landing 工程纸风格(截图见上);Gradio 页仅作为 dist 未构建时的回退。
- 测试:改动前 pytest 基线 2903 collected;改动后全量 2902 passed, 1 skipped;uitest smoke FAIL/ERROR 均为 0。

## 追加改动(用户反馈)

> 用户:"把紫色梯子全部改成黑色就可以"。

- 网格线颜色:浅色主题 `rgba(43,46,140,…)` → `rgba(0,0,0,.07/.15)`(黑);暗色主题黑色不可见,改为中性浅灰白 `rgba(232,233,245,.07/.14)`。文件:frontend/uitest/src/index.css:10-11,26-27,42-43。
- 验证:`npm run build` ✓;`ruff check src tests` → All checks passed!;`pytest --collect-only -q` → 2903/2997 collected。
- 截图对比:docs/reports/shots/uitest_light.png → uitest_light_blackgrid.png;uitest_dark.png → uitest_dark_blackgrid.png。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 服务启动后极短窗口内 /uitest 与 /api/uitest 返回 404 | 启动后立即 curl 得 {"detail":"Not Found"},数秒后 200 | 静态页与 router 在 launch() 之后才能挂到真正服役的 FastAPI 实例(Gradio 6 行为,见 ui.py 注释) | 仅影响启动后前几秒的请求 | 可接受;如需消除可在挂载完成前不打开浏览器 |
| 低 | npm audit 报依赖告警 | npm install 输出 | 传递依赖版本 | 开发期工具链 | 定期 npm update 复查 |
| 低 | React 页的 PWA manifest 无图标 | vite.config.ts icons: [] | 未设计专用图标 | 安装为 PWA 时无图标 | 后续补 SVG 图标 |

## 未执行的步骤

- 真浏览器点击 Run 跑完整套件:未执行 —— 同一时段 CLI smoke 占用被测端口 7912,改以 curl SSE 实测同一后端路径(POST /api/uitest/run,证据见上),页面渲染以截图验证。
