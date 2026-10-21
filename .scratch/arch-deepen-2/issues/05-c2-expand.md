# 05: C2 expand — shared 构建基座 + 2 个试点 workspace

**What to build:** frontend/shared 落 vite.base.ts(makeViteConfig({base, apiPath}):react 插件、@/@shared alias、proxy→7860、outDir)、tsconfig{,.app,.node}.base.json、eslint/tailwind/postcss 基座。试点切 doc_qa 与 issue_triage(vite.config 2 行、tsconfig extends、config re-export),index.html/main.tsx 不动。

**Blocked by:** None(文件与 C1 不相交;实际在 04 后顺序执行)

**Status:** ready-for-agent

- [ ] 两试点 lint+build 全绿,dist 被既有页测服务(跑这两个页测)
- [ ] 其余 23 个 workspace 未动,抽 2 个 build 仍绿
