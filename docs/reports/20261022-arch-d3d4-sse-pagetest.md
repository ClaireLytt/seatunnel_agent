# 批次结果报告:架构深化 D3 后端 sse_stream + D4 页测工厂钩子(2026-10-22)

## 批准依据

> 用户以 `/to-tickets 继续` + `/implement-spec` 延续第二轮评审余下候选(D3/D4);分支沿用 dev 直提。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 票01:common/sse.py 深函数(sse framing + sse_stream:queue/daemon thread/sentinel/异常→error 终局/drain 时序列化)+_NO_KEY 并入;8 份现有实现逐份核对(5 可表达/3 架构不同如实不硬塞);8 个单测 | common/sse.py、tests/test_common_sse.py | ecdcc07 |
| 高 | 票02:4 个 SSE 端点切 sse_stream(code_fix/web_task/orchestrator/data_comparison),uitest 保留 drain(生成器级 finally 释放 _run_lock 的语义 sse_stream 无法表达,仅换 framing);SSE 对外契约零变化;sse.py 入 mypy 白名单 | 5 个 api 文件、pyproject.toml | dd32801(+59/−167) |
| 高 | 票03:页测工厂加 extra_mounts/post_setup/name 钩子;余 5 文件迁移(t2s 的双服务器 chat_page_url 也表达成功);9 文件 12 处内联 zh cookie 收编 zh_page | tests/conftest.py + 14 个页测文件 | d080564(+131/−410) |
| 高 | 票04:收尾验证与本报告 | — | 本报告同批提交 |

**grep 证据**:`def _sse(` src/ 下 3 处=正当保留(text2sql/data_lineage/seatunnel,架构不同:外部会话队列/轮询收集器/多会话锁);`def _free_port` 仅 conftest 一处。

## 验证结果

```
ruff check src tests   -> All checks passed!(exit 0)
mypy                   -> Success: no issues found in 110 source files(含新 sse.py)
pytest -q              -> 3300 passed, 1 skipped, 237 deselected
票级定向:SSE 相关 6 文件 197 passed;5 页测 4 failed+74 passed(4 失败=t2s 无 API_KEY
  既有环境问题,子代理以 HEAD 基线副本实跑对照,失败集合逐一相同,非回归)
uitest smoke --no-llm  -> PASS 22 · FAIL 0(runs/20261022_085014/report.html)
python scripts/check_workflow.py(PYTHONUTF8=1)-> 随收尾执行,输出附对话
```

## 前后差异

- 行数:SSE 样板 −167(5 文件)+ 页测夹具 −410(15 文件)= **净删 ~577 行**,新共享实现 sse.py ~90 行 + conftest 钩子 ~24 行。
- 局部性:SSE framing/哨兵/异常终局协议单点可测(8 个单测);26 个页测文件 0 本地夹具副本;zh cookie 语义单点。
- 杠杆:新流式 agent 的端点=写 work(emit);新页面页测=一行声明(含双 mount/模块打桩形态)。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 子代理触发"Irreversible Local Destruction"安全警告:`rm tests/test_t2s_head_page.py`(其自建的未跟踪 HEAD 对照临时文件,git ls-files/历史均 0 命中,删前有 porcelain 核对) | 本会话核查 | CLAUDE.md §9 字面禁止一切 rm | 无实际损害;但违规形态 | 后续子代理指令加"临时文件也不得 rm";可考虑 §9 补充"自建未跟踪临时文件的清理规范" |
| 低 | t2s 页测 4 例无 API_KEY 失败(既有,HEAD 对照证实) | 票03 实验 | 环境 | 本机全量 uitest 红 | 配 .env 或 fixture skip,另票 |
| 低 | SSE 三份正当保留(text2sql/data_lineage/seatunnel) | grep 证据 | 真架构差异 | 无 | 保持 |
| 低 | PostToolUse 钩子缺 tools/ui_check_hook.py 的报错噪音 | 全程 | settings 配置超前 | 噪音 | 等用户决定补脚本或删配置 |

## 未执行的步骤

无(推送随本批收尾执行,网络不通则后台重试并在对话说明)。
