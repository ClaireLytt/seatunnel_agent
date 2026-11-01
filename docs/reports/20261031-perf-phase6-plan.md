# 方案:性能套件六期(2026-10-31)

四期/五期的新能力目前只在 CLI;六期把其中适合交互的四个搬上
对应 Web 页(API 字段 + React 页面 + API 级测试),贴粘贴即得结论。
慢化趋势(--trend)与加盐 what-if 依赖本地台账/事件日志路径,留在 CLI。

| # | 页面 | 增强 | API 字段 |
| --- | --- | --- | --- |
| W1 | /sqlperf | 可选"优化前计划"输入:贴两份 EXPLAIN 出前后对比节 | `before_text` / `before_file` |
| W2 | /sqlcost | 可选"改写 SQL"输入:同清单各估一次出省比表 | `compare_sql` |
| W3 | /indexadvisor | 带 DDL 时报告自动追加现状审计节(IA001–IA004),与 CLI 对齐 | 无新字段(`ddl` 即触发) |
| W4 | /dagconflict | 可选"准入 DAG"输入:输出最优起点与候选表 | `place` |

## 边界

- 页面只加一个可选输入框/一段渲染,不动布局与配色;文案走 i18n zh/en。
- 每页一个 commit:API+测试 与 前端 一起;prettier 跑过;vite build 过。

## 验证

结果与门禁输出见同批结果报告 docs/reports/20261031-perf-phase6.md:

```
python scripts/check_workflow.py --range origin/main...HEAD ->
[PASS] x6(见结果报告)
```
