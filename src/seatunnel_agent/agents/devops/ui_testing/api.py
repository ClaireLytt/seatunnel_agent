"""REST API for the UI testing agent — FastAPI router.

Backend for the React page served at /uitest (frontend/uitest).
Endpoints:
  GET  /api/uitest/meta                     — suites + agent picker choices
  POST /api/uitest/run                      — run a suite, SSE progress stream
  GET  /api/uitest/report/{run_id}          — report.html inline (iframe src)
  GET  /api/uitest/report/{run_id}/download — report.html as attachment
  POST /api/uitest/case                     — validate & save a YAML case
"""

from __future__ import annotations

import json
import queue
import re
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel

from .catalog import AGENT_LABELS, AGENT_ROUTES, SUITES, agent_case_ids

router = APIRouter(prefix="/api/uitest", tags=["uitest"])

# repo-root dist built by `npm run build` in frontend/uitest
# bundle path comes from the registry convention (frontend/<name>/dist);
# kept as a thin alias for existing importers (tests)
from seatunnel_agent.hub.registry import frontend_dist as _frontend_dist


def _uitest_dist() -> Path:
    from .manifest import MANIFEST
    return _frontend_dist(MANIFEST)


FRONTEND_DIST = _uitest_dist()

_RUN_ID_RE = re.compile(r"^\d{8}_\d{6}$")
_run_lock = threading.Lock()


class RunRequest(BaseModel):
    suite: str = "smoke"
    agent: str = "all"
    case_ids: str = ""
    no_llm: bool = True


class CaseRequest(BaseModel):
    text: str


@router.get("/meta")
def meta() -> dict:
    return {
        "suites": SUITES,
        "agents": [
            {"key": k, "label_en": AGENT_LABELS["en"][k],
             "label_zh": AGENT_LABELS["zh"][k]}
            for k in AGENT_ROUTES
        ],
    }


@router.get("/runs")
def runs() -> dict:
    """History: one entry per runs/<ts>/ with a result.json, newest first."""
    from .runner import RUNS_DIR
    out = []
    if RUNS_DIR.is_dir():
        for d in sorted(RUNS_DIR.iterdir(), reverse=True):
            rj = d / "result.json"
            if not (_RUN_ID_RE.match(d.name) and rj.is_file()):
                continue
            try:
                data = json.loads(rj.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            counts: dict[str, int] = {}
            for c in data.get("cases", []):
                v = c.get("verdict", "")
                counts[v] = counts.get(v, 0) + 1
            out.append({
                "run_id": d.name,
                "suite": data.get("suite", ""),
                "elapsed_ms": data.get("elapsed_ms", 0),
                "counts": counts,
                "has_report": (d / "report.html").is_file(),
            })
    return {"runs": out}


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/run")
def run(req: RunRequest) -> StreamingResponse:
    if req.suite not in SUITES:
        raise HTTPException(status_code=422, detail=f"unknown suite: {req.suite}")
    if not _run_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="a run is already in progress")

    case_ids = [c for c in (req.case_ids or "").replace(",", " ").split() if c]
    if not case_ids and req.agent and req.agent != "all":
        case_ids = agent_case_ids(req.agent)

    def stream():
        from .report import write_html, write_json, write_labels_patch
        from .runner import run_suite

        q: queue.Queue = queue.Queue()
        done: dict = {}

        def progress(i, n, cr):
            q.put(f"[{i}/{n}] {cr.verdict:<6} {cr.case_id:<5} {cr.title} "
                  f"({cr.elapsed_ms / 1000:.1f}s)")

        def work():
            try:
                rr, run_dir = run_suite(suite=req.suite,
                                        case_ids=case_ids or None,
                                        no_llm=req.no_llm,
                                        on_progress=progress)
                write_json(rr, run_dir)
                write_html(rr, run_dir)
                write_labels_patch(rr, run_dir)
                done["rr"] = rr
                done["run_id"] = run_dir.name
            except Exception as e:  # surfaced to the client as an event
                done["error"] = f"{type(e).__name__}: {e}"
            finally:
                q.put(None)

        try:
            t = threading.Thread(target=work, daemon=True)
            t.start()
            while True:
                item = q.get()
                if item is None:
                    break
                yield _sse({"type": "progress", "line": item})
            t.join(timeout=10)

            if "error" in done:
                yield _sse({"type": "error", "message": done["error"]})
                return
            rr = done["rr"]
            yield _sse({
                "type": "done",
                "run_id": done["run_id"],
                "counts": rr.counts(),
                "elapsed_ms": rr.elapsed_ms,
            })
        finally:
            _run_lock.release()

    return StreamingResponse(stream(), media_type="text/event-stream")


def _report_path(run_id: str) -> Path:
    if not _RUN_ID_RE.match(run_id):
        raise HTTPException(status_code=422, detail="bad run id")
    from .runner import RUNS_DIR
    path = RUNS_DIR / run_id / "report.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="report not found")
    return path


@router.get("/report/{run_id}")
def report(run_id: str) -> HTMLResponse:
    return HTMLResponse(_report_path(run_id).read_text(encoding="utf-8"))


@router.get("/report/{run_id}/download")
def report_download(run_id: str) -> FileResponse:
    return FileResponse(_report_path(run_id),
                        filename=f"uitest-report-{run_id}.html",
                        media_type="text/html")


@router.post("/case")
def save_case(req: CaseRequest) -> dict:
    from .loader import USER_CASES_DIR, CaseLoadError, validate_case_yaml
    if not (req.text or "").strip():
        raise HTTPException(status_code=422, detail="empty case YAML")
    try:
        cases = validate_case_yaml(req.text)
    except CaseLoadError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    USER_CASES_DIR.mkdir(parents=True, exist_ok=True)
    path = USER_CASES_DIR / f"{cases[0].id.lower()}.yaml"
    path.write_text(req.text, encoding="utf-8")
    return {"ids": [c.id for c in cases], "path": str(path)}
