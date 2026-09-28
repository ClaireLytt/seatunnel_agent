"""Launch the web UI with INFO logging to stdout (debug session helper)."""
import io
import logging
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stderr,
)

from seatunnel_agent.ui import create_ui, launch_app

app = create_ui()
print("debug UI starting on http://127.0.0.1:7860", flush=True)
launch_app(app, port=7860, host="127.0.0.1", share=False, api=False)
