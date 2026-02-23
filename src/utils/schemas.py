"""Schema validation for ingestion and pipeline records."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ConversationRecord(BaseModel):
    """Raw conversation record from ingestion."""

    user_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message_id: Optional[str] = None


class EnrichedRecord(ConversationRecord):
    """Record with embedding and lineage."""

    embedding: list[float] = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    source_file: Optional[str] = None
