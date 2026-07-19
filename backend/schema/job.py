from pydantic import BaseModel

class JobStatus(BaseModel):
    job_id: str
    status: str  # "queued" | "running" | "done" | "error"
    path: str
    error: str | None = None