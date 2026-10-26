# 批次结果报告:uitest 补课(2026-10-27)

## 批准依据

> 用户对"提交本批 → 做 uitest 补课"方案回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 中高 | 新增 Playwright 用例 ×3:订阅新表单(watch 条件字段/model 隐藏阈值/freshness 滞后/digest 清单 + 端到端建一条 digest 订阅)、健康页(真连接+指标库,断言 gmv 行与昨日日期)、**缓存徽标+结果卡行内容**(零 LLM 全链路,行内容断言正是让空行 bug 存活多日的缺口) | tests/test_t2s_page.py | 本批 |
| 中 | 顺手修:`T2S_EXAMPLES_PATH` 在模块导入时固化 → 改为构造时读环境(与 api_auth 同哲学,长驻服务/测试可重指) | examples.py | 本批 |
| 中 | 既有 lifecycle 用例的 stub 按旧 bug 签名写(`fake_run(sub, store)` 对应端点误传 store 的年代)——修好的端点只传 sub,stub TypeError 被吞成 "—"。stub 改为真实契约(返回 outcome 由端点记录),断言恢复 "ok" | tests/test_t2s_page.py | 本批 |

## 验证结果

```
python -m pytest -m uitest tests/test_t2s_page.py -q -> 21 passed in 80s（18 → 21,全绿）
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 174 source files
python -m pytest -q          -> 3470 passed, 1 skipped, 246 deselected in 159.62s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

调试记录:lifecycle 先红 → 探针证实端点记录正确 → 定位到 stub 的旧签名(测试编码了被修掉的 bug),按真实契约重写 stub;探针已清理。

## 前后差异

- 浏览器回归:18 → 21 条;三批 UI 改动(订阅表单/健康页/缓存徽标)从"人工截图验收"变为自动回归;结果卡行内容首次有断言。
- 非 UI 行为变化仅 examples 路径环境变量读取时机(默认路径不变)。

## 未解决问题 / 遗留清单

无(UI 露出路线图 1–4 全部收口并有回归)。

## 未执行的步骤

无。
