from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.note_repo import NoteRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.user_repo import UserRepository
from app.schemas.note import NoteRead, NoteWithTasksRead
from app.schemas.task import TaskRead
from app.schemas.telegram import TelegramWebhookRequest
from app.services.telegram_service import TelegramService

router = APIRouter(prefix="/telegram", tags=["Telegram"])


def get_telegram_service(db: AsyncSession = Depends(get_db)) -> TelegramService:
    user_repo = UserRepository(db)
    note_repo = NoteRepository(db)
    task_repo = TaskRepository(db)
    return TelegramService(
        user_repo=user_repo,
        note_repo=note_repo,
        task_repo=task_repo,
    )

@router.post("/webhook")
async def telegram_webhook(
    payload: TelegramWebhookRequest,
    service: TelegramService = Depends(get_telegram_service),
):
    return await service.handle_webhook(payload)


@router.get("/users/{telegram_id}/notes", response_model=list[NoteRead])
async def get_user_notes(
    telegram_id: int,
    service: TelegramService = Depends(get_telegram_service),
):
    return await service.get_user_notes(telegram_id)

@router.get("/users/{telegram_id}/notes/{user_note_number}", response_model=NoteWithTasksRead)
async def get_user_note_details(
    telegram_id: int,
    user_note_number: int,
    service: TelegramService = Depends(get_telegram_service),
):
    result = await service.get_user_note_details(telegram_id, user_note_number)
    if not result:
        raise HTTPException(status_code=404, detail="Note not found")

    note, tasks = result
    note_dict = NoteRead.model_validate(note).model_dump()
    note_dict["tasks"] = [TaskRead.model_validate(task).model_dump() for task in tasks]
    return note_dict

@router.post("/users/{telegram_id}/notes/{user_note_number}/tasks", response_model=TaskRead)
async def create_task_from_note(
    telegram_id: int,
    user_note_number: int,
    payload: dict,
    service: TelegramService = Depends(get_telegram_service),
):
    title = payload.get("title")
    description = payload.get("description")
    due_date_text = payload.get("due_date")
    priority = payload.get("priority", "medium")

    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    if priority not in {"low", "medium", "high"}:
        raise HTTPException(status_code=400, detail="priority must be low, medium or high")

    task = await service.create_task_from_note(
        telegram_id=telegram_id,
        user_note_number=user_note_number,
        title=title,
        description=description,
        due_date_text=due_date_text,
        priority=priority,
    )
    if not task:
        raise HTTPException(status_code=404, detail="Note not found")

    return task


@router.patch("/users/{telegram_id}/notes/{user_note_number}", response_model=NoteRead)
async def update_user_note(
    telegram_id: int,
    user_note_number: int,
    payload: dict,
    service: TelegramService = Depends(get_telegram_service),
):
    new_content = payload.get("content")
    if not new_content:
        raise HTTPException(status_code=400, detail="content is required")

    note = await service.update_user_note(
        telegram_id=telegram_id,
        user_note_number=user_note_number,
        new_content=new_content,
    )
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")

    return note


@router.delete("/users/{telegram_id}/notes/{user_note_number}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_note(
    telegram_id: int,
    user_note_number: int,
    service: TelegramService = Depends(get_telegram_service),
):
    deleted = await service.delete_user_note(telegram_id, user_note_number)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)