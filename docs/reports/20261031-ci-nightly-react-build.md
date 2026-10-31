# CI 修复 — ui-nightly React 页面未构建导致 GOV/PD/SLT 全组超时

日期: 2026-10-31 分支: fresh

## 现象

main 定时任务 ui-nightly（run 41244751871 与 41138158933,10-30 起连续两夜）失败：
GOV2-7、PD2-4、SLT2-3 共 11 个用例两轮全部
`TimeoutError: Page.wait_for_function: Timeout 15000ms exceeded`,非 flaky。

## 根因

- 10-29 之前 nightly 全绿;10-30 main 合入 #152,把治理六件套/故障诊断/SLA 追踪的
  **React 页面**用例加进 full 套件。
- `uitest-nightly.yml` 只装 Python 依赖,从不构建前端。`hub/ui.py:mount_react_pages`
  对未构建的 dist 注册 `_unbuilt` 提示页 —— 该页不打 `body[data-st-lang]` 语言戳。
- 用例统一走 `set_language` → `wait_for_function(body.dataset.stLang === want, 15s)`,
  提示页永远不打戳 → 每个 React 页面用例确定性超时。Gradio 页（GOV1 等）在服务端
  打戳,不受影响,所以只挂 React 组。

## 修复

`.github/workflows/uitest-nightly.yml` 的 ui-full job 在跑套件前新增：
setup-node@v7（node 22,npm 缓存指向 frontend/package-lock.json）+
`cd frontend && npm ci && npm run build --workspaces --if-present`,
把全部 workspace 构建成真实页面。ui-hive 套件只打 Gradio 页,不加。

## 验证

```
python -c "yaml.safe_load(...)"  → yaml ok
cd frontend && npm run build --workspace contract_check --if-present
  → ✓ built in 3.46s   （GOV2 对应页面,构建命令逐 workspace 可用）
```

完整验证需等下一次 nightly 调度（或 merge 后 workflow_dispatch 手动触发）。

## Gate

```
[PASS] AI 署名: 无 AI 署名(范围 origin/fresh..HEAD)
[PASS] 工作区: 工作区干净
[PASS] 报告落盘: 代码改动已附带落盘报告
[PASS] 报告含验证输出: 报告含 check_workflow 输出
[PASS] floor: 无作弊变绿改动(范围 origin/fresh..HEAD)
[PASS] 前端锁文件: workspace 与锁文件同步(范围 origin/fresh..HEAD)
```
