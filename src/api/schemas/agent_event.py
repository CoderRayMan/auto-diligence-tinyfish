from __future__ import annotations

from pydantic import BaseModel


class AgentEvent(BaseModel):
    scan_id: str
    source_id: str
    agent_tag: str        # RUNNING | COMPLETED | WAITING | FAILED
    message: str
    timestamp: str        # ISO 8601
