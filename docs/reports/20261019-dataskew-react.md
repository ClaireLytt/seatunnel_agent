# 批次结果报告:Data Skew Analyzer React 迁移(2026-10-19)

## 批准依据

> grilling 七问(整套沿用模式 / 流程分支同上 / 按规模拆票 + recharts 预案 /
> datacompare 会话层 / 上传下载轻量路线(仅事件日志 multipart) / LLM 阻塞
> 无 SSE / 4 票划分)用户回复:"yes";随后用户以 `/implement-spec` 启动实现。
> 分支约束(用户原话):"就在现在的分支开发不允许切换新分支"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票 01:skew 会话注册表(datacompare 模式)+ React-surface 端点(session/connect/status、analyze、verify、consistency、splitkey、runtime×2、history、presets 代理),结构化 {code,message} 守卫;sections.py 抽取;15 条 API 测试 | src/seatunnel_agent/agents/data/data_skew/{registry,sections,api}.py、tests/test_dataskew_session_api.py | bca9fd0 |
| 高 | 票 02:React 页 A — 分析/上传/Blob 下载/SQL 桥接/历史 | frontend/data_skew/ | cb4af91 |
| 高 | 票 03:React 页 B — 连接/预设/cookie 预填/探针/一致性/split-key(补丁下载)/runtime + cutover 退役 Gradio | frontend/data_skew/src/components/、manifest.py、hub/ui.py、tests 重指向 sections.py | f95b396 |
| 高 | 票 04:页测 12 例 + i18n parity(钉现存后端 dsk 字典)+ 触点清理(YAML×4、catalog、page.py、css.py)| tests/test_dataskew_page.py、tests/test_dataskew_i18n.py、ui_testing/*、hub/css.py | (本报告同批 commit) |
| 低 | adhoc fixture 机制测试改用合成 fixture | tests/test_ui_adhoc.py | (同批) |
| 中 | spec 与 4 张票 | .scratch/dataskew-react/ | 8d43cbc |

## 验证结果

```
ruff check src tests   -> All checks passed!
mypy                   -> Success: no issues found in 115 source files
pytest -q              -> 3194 passed, 1 skipped, 117 deselected in 117.30s
pytest tests/test_data_skew.py tests/test_dataskew_session_api.py -> 194 passed
pytest -m uitest tests/test_dataskew_page.py -> 12 passed in 39.65s
npm run lint --workspace data_skew  -> 通过(无输出)
npm run build --workspace data_skew -> ✓ built in 3.04s
uitest smoke (--no-llm) -> PASS 44 · FAIL 0 · ERROR 0 · SKIP 0 · MANUAL 1 · 耗时 169s
                           报告: runs/20261019_020338/report.html
                           (50→44:DSK smoke YAML + SCR9 退役,等价覆盖移入页测)
python scripts/check_workflow.py -> (报告落盘提交后补记,见文末)
```

手工验证:hub 启动后 `GET /dataskew/` 200;`POST /api/skew/session` 发号正常;
中文静态分析往返截图(COUNT(DISTINCT) 规则命中、报告表格、四折叠区)见下。

## 前后差异

- 测试:3176 → 3194 passed(+15 会话 API、+5 parity、-2 退役的 DSK 标签同步
  测试等),0 失败。YAML DSK1-DSK21/DSKA1/SCR9/fixture → 页测 12 例等价
  (DSKA1 真 LLM 留手动;LLM 路径以 llm_unavailable 回退在 API 层确定性覆盖)。
- API:新增 9 组端点(见上);现有 `/check`、`/health` 契约不变(全部测试通过)。
- UI 截图(before = Gradio,after = React):
  - docs/reports/shots/dataskew-gradio-before-zh-light.png → dataskew-react-zh-report.png
  - docs/reports/shots/dataskew-gradio-before-en-dark.png → dataskew-react-en-dark.png
  - 全套 9 张在 .scratch/dataskew-react/screenshots/

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | 后端 i18n.py 的 UI chrome 键(dsk_host 等)未裁剪 | grep 零死键(parity 测试与动态取键引用) | parity 测试钉在现存字典上,裁剪会破坏钉定 | 字典略冗余 | 保持——它现在是 React 文案的单一事实来源 |
| 低 | /presets/{name} 返回明文密码(与 Gradio 预填行为 1:1) | api.py presets_get | 旧页同样把密码填进表单 | 同源页面可读;公网部署需注意 | 如需收紧可改为服务端占位 + connect 时引用预设名 |
| 低 | /analyze llm 模式为长阻塞请求(无超时控制) | api.py analyze | 1:1 保持 Gradio 阻塞行为(grilling Q6) | 极端情况下占用 worker | 未来可加服务端超时或移步 SSE |
| 低 | hub include_router 已第 9 份拷贝 | hub/ui.py | 文档先例模式 | 维护噪音 | 未来 registry 驱动统一挂载 |

## 未执行的步骤

- 无。
