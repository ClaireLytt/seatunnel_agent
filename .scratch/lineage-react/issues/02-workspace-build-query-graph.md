# 02: React 页 A — 骨架 + 建图 + 查询 + Mermaid 图

**What to build:** 用户在 React `/lineage` 完成核心闭环：配置数据源
（SQL 目录+方言 / SeaTunnel 目录 / Hive 开关+高级折叠）→ 建图看统计、
表下拉填充 → 选表/方向/深度/字段查询 → 可点击 Mermaid 图（npm 包渲染，
节点点击重查）+ 报告 + Mermaid 源折叠。zh/en 与暗色正确。

**Blocked by:** 01 (API 层)

**Status:** ready-for-agent

- [ ] before 截图（zh/en × 亮/暗）存 .scratch/lineage-react/screenshots/（退役前）
- [ ] workspace frontend/data_lineage（data_skew 参照），mermaid npm 锁版本
- [ ] 数据源区 + 建图（stats 行、下拉填充、need_source/bad_dir 提示）
- [ ] 查询区（表下拉可自定义输入、方向、深度滑杆、字段）→ 图+报告+源折叠
- [ ] 节点点击 → 置表名并重查（替代 iframe 跳桥）
- [ ] i18n ~55 键原样搬；暗色下 mermaid 主题随 @shared
- [ ] ruff / mypy / workspace lint+build 通过（尚不 cutover）
