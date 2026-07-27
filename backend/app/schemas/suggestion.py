import uuid
from datetime import datetime

from pydantic import BaseModel


class SuggestionResponse(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    suggestion_type: str
    content: str
    severity: str | None = None
    accepted: bool | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SuggestionUpdate(BaseModel):
    accepted: bool
