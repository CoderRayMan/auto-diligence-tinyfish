from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


class AgentEvent(BaseModel):
    scan_id: str
    source_id: str
    agent_tag: str              # RUNNING | COMPLETED | WAITING | FAILED | STREAMING_URL
    message: str
    timestamp: str              # ISO 8601
    streaming_url: Optional[str] = None  # Live browser stream URL from TinyFish
