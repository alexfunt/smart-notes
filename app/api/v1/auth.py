from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.note_repo import NoteRepository
from app.repositories.user_repo import UserRepository
from app.repositories.task_repo import TaskRepository
from app.schemas.telegram import TelegramAuthRequest, TelegramWebAppAuthRequest
from app.schemas.user import UserRead
from app.services.telegram_service import TelegramService
from app.utils.telegram_webapp import WebAppAuthError

router = APIRouter(prefix="/auth", tags=["Auth"])


def get_telegram_service(db: AsyncSession = Depends(get_db)) -> TelegramService:
    user_repo = UserRepository(db)
    note_repo = NoteRepository(db)
    task_repo = TaskRepository(db)

    return TelegramService(
        note_repo=note_repo,
        user_repo=user_repo,
        task_repo=task_repo,
    )


@router.post("/telegram", response_model=UserRead)
async def auth_telegram(
    payload: TelegramAuthRequest,
    service: TelegramService = Depends(get_telegram_service),
):
    return await service.auth_telegram_user(payload)


@router.post("/telegram/webapp", response_model=UserRead)
async def auth_telegram_webapp(
    payload: TelegramWebAppAuthRequest,
    service: TelegramService = Depends(get_telegram_service),
):
    """Авторизация из Telegram Mini App: HMAC-проверка initData."""
    try:
        return await service.auth_telegram_webapp(payload.init_data)
    except WebAppAuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        )