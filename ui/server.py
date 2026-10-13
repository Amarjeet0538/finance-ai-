"""FastAPI web dashboard for observing the operator and processing human approvals."""

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from agent.event_bus import emit, poll_events
from agent.state import TaskState

app = FastAPI(title="CenterAlign Operator Live Dashboard")

# Mount static and screenshots
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_DIR = REPORTS_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory="ui/static"), name="static")
app.mount("/screenshots", StaticFiles(directory=str(SCREENSHOTS_DIR)), name="screenshots")

templates = Jinja2Templates(directory="ui/templates")


@app.get("/", response_class=HTMLResponse)
async def dashboard_index(request: Request, run_id: Optional[str] = None):
    # If run_id not provided, look for the most recent state file in reports
    active_run_id = run_id
    if not active_run_id:
        state_files = sorted(REPORTS_DIR.glob("state_*.json"), key=os.path.getmtime, reverse=True)
        if state_files:
            active_run_id = state_files[0].stem.replace("state_", "")
        else:
            active_run_id = "default_run"

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={"run_id": active_run_id},
    )


@app.get("/ui/runs")
async def list_runs():
    """List available runs for dropdown selection."""
    state_files = sorted(REPORTS_DIR.glob("state_*.json"), key=os.path.getmtime, reverse=True)
    runs = [f.stem.replace("state_", "") for f in state_files]
    return {"runs": runs}


@app.get("/ui/state/{run_id}")
async def get_state(run_id: str):
    """Retrieve state snapshot for run."""
    state = TaskState.load(run_id)
    if not state:
        return {"error": "Run not found"}
    return state.to_dict()


@app.get("/ui/report/{run_id}")
async def get_report(run_id: str):
    """Return markdown report content if generated."""
    report_file = REPORTS_DIR / f"run_{run_id}_report.md"
    if not report_file.exists():
        report_file = REPORTS_DIR / "sample_run_report.md"
    if report_file.exists():
        return {"report": report_file.read_text(encoding="utf-8")}
    return {"report": "Report not yet generated for this run."}


@app.post("/ui/approval/{run_id}/{claim_id}")
async def submit_approval(run_id: str, claim_id: str, request: Request):
    """Receive human decision from dashboard and write to event bus."""
    data = await request.json()
    decision = str(data.get("decision", "DENIED")).upper()
    note = data.get("note", "Decided via web dashboard")

    emit(
        run_id=run_id,
        event_type="approval_response",
        payload={
            "claim_id": claim_id,
            "decision": decision,
            "note": note,
        },
    )
    return {"status": "ok", "decision": decision, "claim_id": claim_id}


@app.get("/ui/events/{run_id}")
async def stream_events(run_id: str, request: Request):
    """Server-Sent Events (SSE) streaming operational events from events_<run_id>.db."""
    async def event_generator():
        last_id = 0
        while True:
            if await request.is_disconnected():
                break

            events = poll_events(run_id=run_id, since_id=last_id)
            for ev in events:
                last_id = ev["id"]
                data_str = json.dumps(ev)
                yield f"data: {data_str}\n\n"

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
