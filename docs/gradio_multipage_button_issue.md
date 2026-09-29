# Draft: gradio issue — Button `interactive=False` update never applies on multipage routes

> Status: DRAFT — 提交到 github.com/gradio-app/gradio 前需要确认。
> 先搜索是否已有同类 issue;若有,补充复现代码即可。

## Title

`gr.update(interactive=False)` / `gr.Button(interactive=False)` returned from an
event handler is never applied when the Button lives in a multipage
`app.route()` page (works on a single-page Blocks)

## Environment

- gradio 6.26.0, Python 3.13, Windows 11 / also reproduced headless Chromium+Edge

## Reproduction

Single-page — WORKS (button gets the `disabled` attribute within ~1s):

```python
import time
import gradio as gr

def slow():
    time.sleep(6)
    return "done"

with gr.Blocks() as demo:
    btn = gr.Button("Run")
    out = gr.Textbox()
    btn.click(lambda: gr.update(interactive=False), outputs=[btn]
    ).then(slow, outputs=[out]
    ).then(lambda: gr.update(interactive=True), outputs=[btn])

demo.launch()
```

Multipage — BROKEN (same wiring, `el.disabled` never becomes true; verified by
sampling the DOM every 400ms during the run with Playwright):

```python
import time
import gradio as gr

def slow():
    time.sleep(6)
    return "done"

with gr.Blocks() as demo:
    gr.Markdown("hub")

with demo.route("Page", "/page"):
    btn = gr.Button("Run")
    out = gr.Textbox()
    btn.click(lambda: gr.update(interactive=False), outputs=[btn]
    ).then(slow, outputs=[out]
    ).then(lambda: gr.update(interactive=True), outputs=[btn])

demo.launch()
```

- `gr.Button(interactive=False)` as the return value behaves identically.
- The `slow` handler's own output (Textbox) DOES render on the multipage route,
  so the event chain runs and the queue delivers other updates — only the
  Button interactive update is lost.
- Workaround we shipped: `trigger_mode="once"` on the click (drops duplicate
  clicks while pending), giving up on the visual disabled state.

## Why it matters

Disabling a button during a long-running job is the standard double-click
guard; on multipage apps it silently does nothing, so apps believe they are
protected while duplicate jobs still queue.
