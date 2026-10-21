# 02: D1 expand — @shared 四件套 + 2 试点页

**What to build:** frontend/shared 落 PageHeader({badge, maxW?},标题/副标题走 i18n title/subtitle keys,含 home 链接)、useRunner(fn)→{busy,error,result,run}(catch 归一 ⚠️、zh/en 归一)、initI18n(resources)、fetchJson(url,init)(统一抛 ApiError{status,detail});constants 加 btnPrimary/btnGhost。试点切 doc_qa 与 issue_triage(App.tsx 用四件套、i18n.ts 只剩词典、api.ts 用 fetchJson);外观零变化。

**Blocked by:** None(与 01 不相交)

**Status:** ready-for-agent

- [ ] 两试点 lint+build 绿;页测(docqa/triage)绿;其余 23 页抽 2 个 build 仍绿
- [ ] 试点 App/i18n/api 三文件合计显著瘦身(汇报行数)
