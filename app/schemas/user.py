from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    telegram_id: int | None = None
    username: str | None = None
    full_name: str | None = None
    email: EmailStr | None = None
    timezone: str = "UTC"


class UserCreate(UserBase):
    pass


class UserRead(UserBase):
    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)