"""
api.py

FastAPI wrapper around the existing scan pipeline (TODO item 14), plus a
simple in-memory background job queue (TODO item 16) so POST /scan
doesn't block on large repos — it enqueues a job and returns immediately,
and the caller polls GET /jobs/{job_id} for status/result (or opens the
WebSocket at /jobs/{job_id}/ws to get pushed updates instead of polling).

This is an in-process asyncio queue, not a durable broker (no Redis/
Celery) — jobs are lost on process restart. That's a deliberate scope
cut: a durable queue is an infra decision (which broker, deployment
topology) that belongs with whoever's actually running this as a
service, not baked into the library. Swapping the queue implementation
later only touches _run_scan_job / the worker loop below.

Endpoints:
  POST /scan          {"path": "..."}         -> {"job_id": "..."}
  GET  /jobs                                   -> recent jobs (list)
  GET  /jobs/{job_id}                          -> {"status": ..., "result": ...}
  WS   /jobs/{job_id}/ws                       -> pushed status updates
  GET  /graph          ?job_id=...             -> the graph portion of a completed job
  GET  /unresolved      ?job_id=...            -> the unresolved portion of a completed job
  POST /context        {"job_id", "changed_functions", ...} -> LLM context bundle

Run with: uvicorn api:app --reload

CORS: enabled for local frontend dev (see ALLOWED_ORIGINS below) so the
code-analyzer-UI Vite dev server can call this from the browser. Without
this, every request from the UI fails with an opaque CORS error before
it even reaches these route handlers.
"""

import asyncio
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from utils.directory.lookup import get_files_respecting_gitignore, is_exist
from utils.graph.function_graph import build_function_graph
from cache import build_module_graph_incremental
from llm_context import build_context_bundle

# Vite's default dev port is 5173; include both localhost and 127.0.0.1
# since browsers treat them as distinct origins. Override/extend via the
# ANALYZER_UI_ORIGINS env var (comma-separated) for non-default setups —
# e.g. a different Vite port or a deployed UI origin.
_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
ALLOWED_ORIGINS = (
    os.environ.get("ANALYZER_UI_ORIGINS", "").split(",")
    if os.environ.get("ANALYZER_UI_ORIGINS")
    else _default_origins
)


class ScanRequest(BaseModel):
    path: str
    use_cache: bool = True


class JobStatus(BaseModel):
    job_id: str
    status: str  # "queued" | "running" | "done" | "error"
    path: str
    error: str | None = None


class ContextRequest(BaseModel):
    job_id: str
    changed_functions: list[str]
    max_tokens: int = 8000
    include_git_info: bool = True


# In-memory job store + queue. Fine for a single-process deployment;
# see module docstring for the durable-queue caveat. Each job also owns
# an asyncio.Condition, used to push status changes to any open
# WebSocket for that job (see job_ws below) instead of making clients
# poll GET /jobs/{job_id} on an interval.
_jobs: dict[str, dict] = {}
_queue: asyncio.Queue = asyncio.Queue()
_worker_task: asyncio.Task | None = None


def _job_public_view(job: dict) -> dict:
    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "path": job["path"],
        "error": job.get("error"),
        "stats": job.get("stats"),
        "created_at": job.get("created_at"),
    }


async def _worker():
    while True:
        job_id = await _queue.get()
        job = _jobs[job_id]
        async with job["_condition"]:
            job["status"] = "running"
            job["_condition"].notify_all()
        try:
            files = get_files_respecting_gitignore(job["path"])
            result, stats = await asyncio.to_thread(
                build_module_graph_incremental, job["path"], files
            )
            job["result"] = result
            job["stats"] = stats
            async with job["_condition"]:
                job["status"] = "done"
                job["_condition"].notify_all()
        except Exception as e:  # noqa: BLE001 — surface any failure to the poller
            job["error"] = str(e)
            async with job["_condition"]:
                job["status"] = "error"
                job["_condition"].notify_all()
        finally:
            _queue.task_done()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task
    _worker_task = asyncio.create_task(_worker())
    yield
    _worker_task.cancel()


app = FastAPI(title="code-analyzer API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.post("/scan")
async def scan(req: ScanRequest) -> dict:
    existence = is_exist(req.path.strip())
    if existence != "exists":
        raise HTTPException(status_code=400, detail=f"path {existence}")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "path": req.path,
        "result": None,
        "error": None,
        "created_at": time.time(),
        "_condition": asyncio.Condition(),
    }
    await _queue.put(job_id)
    return {"job_id": job_id}


@app.get("/jobs")
async def list_jobs(limit: int = 50) -> dict:
    """Recent jobs, most recently created first. Exists so a UI can show
    "your recent scans" without having to keep its own client-side
    history of job ids returned by POST /scan (the only way to see a
    job before this was to already have its id).
    """
    jobs = sorted(
        _jobs.values(), key=lambda j: j.get("created_at", 0), reverse=True
    )[:limit]
    return {"jobs": [_job_public_view(j) for j in jobs]}


@app.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="unknown job_id")
    return _job_public_view(job)


@app.websocket("/jobs/{job_id}/ws")
async def job_ws(websocket: WebSocket, job_id: str):
    """Pushed job-status updates, as an alternative to polling
    GET /jobs/{job_id} on an interval — matters most for large repos
    where a scan can sit in "running" for a while. Sends the current
    status immediately on connect, then again every time it changes,
    and closes the socket once the job reaches a terminal state
    ("done"/"error") since there's nothing further to push.
    """
    job = _jobs.get(job_id)
    if not job:
        await websocket.close(code=4404)
        return

    await websocket.accept()
    condition = job["_condition"]
    try:
        await websocket.send_json(_job_public_view(job))
        async with condition:
            while job["status"] not in ("done", "error"):
                await condition.wait()
                await websocket.send_json(_job_public_view(job))
    except WebSocketDisconnect:
        pass


def _completed_job_or_404(job_id: str) -> dict:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="unknown job_id")
    if job["status"] != "done":
        raise HTTPException(
            status_code=409, detail=f"job is {job['status']}, not done yet"
        )
    return job


@app.get("/graph")
async def get_graph(job_id: str) -> dict:
    job = _completed_job_or_404(job_id)
    return job["result"]["graph"]


@app.get("/unresolved")
async def get_unresolved(job_id: str) -> dict:
    job = _completed_job_or_404(job_id)
    return {"unresolved": job["result"]["unresolved"]}


@app.get("/function-edges")
async def get_function_edges(job_id: str) -> dict:
    job = _completed_job_or_404(job_id)
    return {"function_edges": job["result"]["function_edges"]}


@app.post("/context")
async def get_context(req: ContextRequest) -> dict:
    """LLM context bundle for a set of changed functions, scoped to an
    already-completed scan job (so we know which path/files to build the
    function-level call graph from). The function graph itself isn't
    part of what /scan computes (that's module-level only, see cache.py)
    so it's built fresh here — cheap relative to the module scan since
    it's a pure AST pass with no filesystem-hash bookkeeping, and it's
    only done for a small requested set of functions' neighborhoods, not
    persisted the way the module graph cache is.
    """
    job = _completed_job_or_404(req.job_id)
    files = get_files_respecting_gitignore(job["path"])
    function_graph = await asyncio.to_thread(build_function_graph, files, job["path"])

    unknown = [fid for fid in req.changed_functions if fid not in function_graph]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"unknown function id(s), not in this job's function graph: {unknown}",
        )

    return await asyncio.to_thread(
        build_context_bundle,
        function_graph,
        req.changed_functions,
        req.max_tokens,
        job["path"],
        req.include_git_info,
    )
