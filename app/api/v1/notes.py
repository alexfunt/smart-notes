from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.note_repo import NoteRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.user_repo import UserRepository
from app.schemas.note import NoteCreate, NoteRead, NoteUpdate
from app.services.note_service import NoteService

router = APIRouter(prefix="/notes", tags=["Notes"])


def get_note_service(db: AsyncSession = Depends(get_db)) -> NoteService:
    user_repo = UserRepository(db)
    note_repo = NoteRepository(db)
    task_repo = TaskRepository(db)
    return NoteService(
        note_repo=note_repo,
        user_repo=user_repo,
        task_repo=task_repo,
    )

@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
async def create_note(
    payload: NoteCreate,
    service: NoteService = Depends(get_note_service),
):
    return await service.create_note(payload)


@router.get("", response_model=list[NoteRead])
async def get_notes(service: NoteService = Depends(get_note_service)):
    return await service.get_notes()


@router.get("/{note_id}", response_model=NoteRead)
async def get_note(note_id: int, service: NoteService = Depends(get_note_service)):
    note = await service.get_note(note_id)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.patch("/{note_id}", response_model=NoteRead)
async def update_note(
    note_id: int,
    payload: NoteUpdate,
    service: NoteService = Depends(get_note_service),
):
    note = await service.update_note(note_id, payload)
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: int, service: NoteService = Depends(get_note_service)):
    deleted = await service.delete_by_id(note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Note not found")
    return None