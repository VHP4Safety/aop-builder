from datetime import datetime
from typing import List, Dict, Optional
from pydantic import BaseModel, Field
import enum

class SessionStatusEnum(str, enum.Enum):
    queued = "queued"
    starting = "starting"
    chunking = "chunking"
    waiting = "waiting"
    extracting = "extracting"
    enriching = "enriching"
    finished = "finished"
    canceled = "canceled"

class CerSessionLogOut(BaseModel):
    id: int
    timestamp: datetime
    status: SessionStatusEnum

    class Config:
        orm_mode = True

class CerSessionBase(BaseModel):
    user_id: int
    collection_id: int
    title: str  # ✅ Added title
    key_events: List[str]
    model_name: str  # ✅ Added model name
    relevance_score_threshold: float = Field(..., ge=1, le=100)

class CerSessionCreate(CerSessionBase):
    pass

class SessionTelemetryOut(BaseModel):
    phase: Optional[str] = None
    model_name: Optional[str] = None
    total_chunks: int = 0
    processed_chunks: int = 0
    successful_chunks: int = 0
    failed_chunks: int = 0
    total_relationships: int = 0
    percent_complete: float = 0
    started_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_chunk_id: Optional[str] = None
    last_message: Optional[str] = None
    last_error: Optional[str] = None

class CerSessionOut(CerSessionBase):
    id: int
    status: SessionStatusEnum
    created_at: datetime
    updated_at: datetime
    logs: List[CerSessionLogOut] = []
    documents: List[Dict] = []
    telemetry: Optional[SessionTelemetryOut] = None

    class Config:
        orm_mode = True

class SessionStatusUpdate(BaseModel):
    status: SessionStatusEnum
