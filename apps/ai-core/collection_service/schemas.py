from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class CollectionCreate(BaseModel):
    user_id: int
    name: str
    description: Optional[str] = None

class CollectionOut(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    pdf_ids: List[str] = []
    status: str
    total_chunks: Optional[int] = 0

    class Config:
        orm_mode = True
