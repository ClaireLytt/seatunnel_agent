# 01: D3 — common/sse.py 的 sse_stream(TDD)

**What to build:** 深函数 `sse_stream(work_fn, *, on_step) -> StreamingResponse`:内部 queue+daemon thread+sentinel;work_fn(emit)(或 on_step 序列化回调,以现有 8 份调用形状最大公约数为准设计)每步经 on_step 序列化为 dict 推送 `data: {json}\n\n`;work_fn 异常 → 推 `{"type":"error","message":"Type: msg"}` 终局;正常结束由 work_fn 返回值经 done 序列化(或 work_fn 自行 emit done,取更贴合 8 份现状者)。另:_NO_KEY 双语 dict 并入 common(code_fix/web_task 两份逐字相同)。单测:事件顺序、异常→error、哨兵正常收尾、ensure_ascii=False。

**Blocked by:** None

**Status:** ready-for-agent

- [ ] 单测绿;ruff/mypy 绿
- [ ] 接口能表达全部 8 份现有变体(设计时逐份核对,表达不了的变体如实记录)
