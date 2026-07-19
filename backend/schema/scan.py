from pydantic import BaseModel

class ScanRequest(BaseModel):
    path: str
    use_cache: bool = True