from pydantic import BaseModel


class TelegramAuthRequest(BaseModel):
    telegram_id: int
    username: str | None = None
    full_name: str | None = None


class TelegramUserInfo(BaseModel):
    id: int
    is_bot: bool = False
    first_name: str | None = None
    last_name: str | None = None
    username: str | None = None


class TelegramChatInfo(BaseModel):
    id: int
    type: str


class TelegramMessage(BaseModel):
    message_id: int
    from_user: TelegramUserInfo
    chat: TelegramChatInfo
    text: str | None = None


class TelegramWebhookRequest(BaseModel):
    update_id: int
    message: TelegramMessage | None = None