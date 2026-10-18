# 前端日常开发(免构建 HMR 路径)

日常迭代 React 页面时不需要走 `--build` 全量构建,用"后端 + Vite dev server"组合即可获得 HMR 热更新。

## 用法

1. 启动后端(端口 7860,不构建前端):

   ```bash
   seatunnel-agent ui
   ```

2. 另开终端,在 `frontend/` 下启动目标 workspace 的 Vite dev server:

   ```bash
   cd frontend
   npm run dev --workspace <name>   # 如 text2sql / sql_review / uitest / data_comparison / seatunnel
   ```

   浏览器访问 Vite 输出的地址(默认 5173)。改动 `frontend/<name>/src` 与 `frontend/shared/src` 即时热更新。

3. API 代理已在各 workspace 的 `frontend/<name>/vite.config.ts` 中配置,
   把 `/api/<name>` 代理到 `http://127.0.0.1:7860`,前端代码无需改接口地址。

## 边界:何时仍需 `--build`

以下场景依赖真实构建产物(dist 静态挂载),必须用:

```bash
seatunnel-agent ui --build
```

- 批次验证 / 批次收尾。
- uitest 截图与 smoke 套件(`python -m seatunnel_agent.agents.devops.ui_testing run --suite smoke --no-llm`),引擎访问的是 hub 挂载的 dist 页面,不是 Vite dev server。
- 验证 hub 静态挂载、路由、manifest 等与构建产物相关的行为。
