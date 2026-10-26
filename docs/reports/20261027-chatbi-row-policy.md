# 批次结果报告:行级权限 v1(2026-10-27)

## 批准依据

> 用户对"两个重件圈选其一,继续 go on 我按 1(行级权限)开工"回复:"go on"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | `policies.py`:策略文件加载(`config/t2s_policies.yaml`/`T2S_POLICIES_PATH`)、`T2S_POLICY` 激活(调用时读环境;指向未定义策略=硬错误);`apply_row_filters` sqlglot 改写——每个 Select 直读的策略表 AND 进条件(裸列自动带表别名),覆盖 JOIN/子查询/UNION;解析失败 PolicyError **失败关闭** | policies.py(新) | 本批 |
| 高 | 执行器工厂单一闸口:`create_executor` 返回策略代理(无策略时原样)——对话/REST/MCP/订阅/看板/周报全链路一个注入点 | executor/base.py | 本批 |
| — | 指南"行级权限"节(明示:服务端环境激活、不接受客户端传入;按 key 区分待多 key 鉴权) | docs/chat_bi_guide.md | 本批 |

新增测试 9 条:改写正确性(简单/别名限定/JOIN 双表/子查询/UNION 双臂/无关表零改动)、失败关闭、配置加载与激活(未定义硬错)、**execute_sql 端到端**(策略开 SUM=40 只见 app 行,策略关 SUM=60 全量——证明过滤来自策略层)。

## 验证结果

```
ruff check src tests scripts -> All checks passed!
mypy                         -> Success: no issues found in 175 source files
python -m pytest tests/test_text2sql_policies.py -q -> 9 passed
python -m pytest -q          -> 3481 passed, 1 skipped, 246 deselected in 165.99s
python scripts/check_workflow.py(提交后终检):
[PASS] AI 署名 / [PASS] 工作区 / [PASS] 报告落盘 / [PASS] 报告含验证输出 / [PASS] floor
```

## 前后差异

- 测试:3472 → 3481 passed(+9)。
- 行为:未设 `T2S_POLICY` 时零变化;设了之后所有执行路径的策略表行被统一过滤,安全纵深从"表白名单+强制LIMIT+列脱敏+成本护栏"补上"行过滤"一层。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 中 | 策略为全服务单选(T2S_POLICY),按 API key/会话区分需多 key 鉴权体系 | policies.py 文档 | 现有 SEATUNNEL_API_KEY 单 key | 多租户隔离暂不可做 | 立项多 key 鉴权后把 key→policy 映射接到 require_api_key |
| 低 | 策略条件本身未过语法白名单(由运维写入服务端文件,信任边界同 metrics.yaml) | load_policies | 配置即信任 | 运维写错条件→执行报错(可见) | 可选:加载时 sqlglot 预解析校验 |

## 未执行的步骤

- uitest smoke:未执行(无 UI/前端改动)。
- 其余无。
