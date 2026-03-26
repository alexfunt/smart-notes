from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TaskBase(BaseModel):
    title: str
    description: str | None = None
    priority: str = "medium"
    status: str = "pending"
    due_date: datetime | None = None
    ai_generated: bool = False


class TaskCreate(TaskBase):
    user_id: int
    note_id: int | None = None
    user_task_number: int | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    priority: str | None = None
    status: str | None = None
    due_date: datetime | None = None
    ai_generated: bool | None = None
    note_id: int | None = None


class TaskRead(TaskBase):
    id: int
    user_id: int
    user_task_number: int
    note_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)