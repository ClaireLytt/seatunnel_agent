# 批次结果报告:text2sql 重构票 #63 共享前端层(2026-10-17)

## 批准依据

> 拆票方案经用户 /implement 批准;UI 人工过目后用户回复:"确认"。

## 已完成

| 优先级 | 内容 | 文件 | commit |
| --- | --- | --- | --- |
| 高 | 新建 frontend/shared(theme.css / sse.ts / lang.ts / utils.ts / components/card.tsx / tailwind-preset.ts),frontend/ 升级 npm workspace | frontend/shared/*, frontend/package.json | 3f951b4 + 本次评审修正 commit |
| 高 | uitest 切换 @shared 引用,删除本地重复实现;CI 两个 workflow 适配 workspace | frontend/uitest/*, .github/workflows/{lint,uitest}.yml | 同上 |

## 代码评审(双轴)后的修正

- uitest 显式声明 `@seatunnel/shared` workspace 依赖(Standards 轴:机制自洽)
- SSE 错误信息恢复 `run:` 前缀(Spec 轴:零行为变化的回归)
- tailwind token 映射抽为 shared/tailwind-preset.ts(Spec 轴:消除下一个 app 将要复制的重复)
- Standards 轴"单消费者预先抽象"按父 spec #62 决议接受(#63 即 #64 的 prefactor 票);"workspace 是死机制"不成立 —— workspace 的作用是把 shared 自身依赖(clsx/tailwind-merge/@types/react)提升到 frontend/node_modules 供 tsc 解析

## 验证结果

```
npm run build / lint / prettier --check -> 全过
pytest -m uitest tests/test_uitest_page.py -> 1 passed
ruff check src tests -> All checks passed!(Python 零改动)
python scripts/check_workflow.py -> 输出附于本批最终 commit 后(见对话)
```

## 前后差异

- 结构:主题/SSE/i18n/卡片从 uitest 内联实现迁至 frontend/shared;行为与视觉不变。
- 截图等价性:uitest_{light,dark}_black.png(改前)vs uitest_{light,dark}_shared.png(改后)—— 配色/布局/字体一致;表单块存在 ~8px 垂直偏移(容差内),历史区行数差异来自 runs/ 自动清理,与本票无关。

## 未解决问题 / 遗留清单

| 优先级 | 问题 | 证据 | 原因 | 影响 | 建议处理方式 |
| --- | --- | --- | --- | --- | --- |
| 低 | workspace 三处命名风格不一(seatunnel-frontend / @seatunnel/shared / uitest-frontend) | package.json ×3 | 渐进演化 | 观感 | #64 建 app 时统一为 @seatunnel/* |
| 低 | .claude/settings.json 引用的 tools/ui_check_hook.py 不存在,每次写文件报 hook 错 | settings.json:75 | 脚本未创建 | 噪音 | 等用户定:补脚本或删条目 |

## 未执行的步骤

- 全量 pytest:未执行 —— 本票 Python 零改动(仅 frontend/ 与 CI yaml),以 ruff + uitest 页冒烟代替;全量套件在 #64(含后端改动)时执行。
