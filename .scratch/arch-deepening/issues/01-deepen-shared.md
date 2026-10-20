# 01: Expand @shared — absorb ReportView, ApiError, DIALECTS, and layout constants

**What to build:** All 13 ReportView clones, 15 ApiError/fetchAgent clones, the DIALECTS array, and CSS class constants move into `@shared`. Every workspace imports them instead of owning copies. All workspaces build and pass lint.

**Blocked by:** None (can start immediately).

**Status:** ready-for-agent

- [ ] ReportView component lives in `@shared/components/` and all 13 workspaces import it
- [ ] ApiError class and a generic `fetchAgent()` helper live in `@shared/api/` and all 15 workspaces import them
- [ ] DIALECTS array exported from `@shared/constants/` and all workspaces importing it
- [ ] CSS class constants (fieldCls, labelCls, textareaCls) exported from `@shared/constants/`
- [ ] All workspace copies of the above are deleted
- [ ] `npm run build --workspaces` passes
- [ ] `npm run lint --workspaces` passes (if configured)
