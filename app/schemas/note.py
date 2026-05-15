from datetime import datetime

from pydantic import BaseModel, ConfigDict
from app.schemas.task import TaskRead


class NoteBase(BaseModel):
    title: str
    content: str
    source: str = "web"
    note_type: str = "plain"
    status: str = "active"
    metadata_json: dict | None = None


class NoteCreate(NoteBase):
    user_id: int
    user_note_number: int | None = None


class NoteUpdate(BaseModel):
    title: str | None = None
    content: str | None = None
    source: str | None = None
    note_type: str | None = None
    status: str | None = None
    metadata_json: dict | None = None


class NoteRead(NoteBase):
    id: int
    user_id: int
    user_note_number: int
    focus_score: float = 0.5
    last_focus_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)

class NoteWithTasksRead(NoteRead):
    tasks: list[TaskRead] = []