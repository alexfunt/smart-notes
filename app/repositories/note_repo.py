from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note
from app.schemas.note import NoteCreate, NoteUpdate


class NoteRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: NoteCreate) -> Note:
        payload = data.model_dump()

        if "user_note_number" not in payload or payload["user_note_number"] is None:
            payload["user_note_number"] = await self.get_next_user_note_number(payload["user_id"])

        note = Note(**payload)
        self.db.add(note)
        await self.db.commit()
        await self.db.refresh(note)
        return note

    async def get_all(self) -> list[Note]:
        result = await self.db.execute(select(Note).order_by(Note.id.desc()))
        return list(result.scalars().all())

    async def get_all_by_user_id(self, user_id:int) -> list[Note]:
        result = await self.db.execute(
            select(Note)
            .where(Note.user_id == user_id)
            .order_by(Note.id.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, note_id: int) -> Note | None:
        result = await self.db.execute(select(Note).where(Note.id == note_id))
        return result.scalar_one_or_none()

    async def get_by_id_and_user_id(self, note_id: int, user_id: int) -> Note | None:
        result = await self.db.execute(
            select(Note).where(
                Note.id == note_id,
                Note.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_by_user_note_number(self, user_id: int, user_note_number: int) -> Note | None:
        result = await self.db.execute(
            select(Note).where(
                Note.user_id == user_id,
                Note.user_note_number == user_note_number,
            )
        )
        return result.scalar_one_or_none()

    async def update(self, note: Note, data: NoteUpdate) -> Note:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(note, field, value)

        await self.db.commit()
        await self.db.refresh(note)
        return note

    async def delete(self, note: Note) -> None:
        user_id = note.user_id

        await self.db.delete(note)
        await self.db.commit()

        await self.reorder_user_notes(user_id)

    async def reorder_user_notes(self, user_id: int) -> None:
        result = await self.db.execute(
            select(Note)
            .where(Note.user_id == user_id)
            .order_by(Note.created_at.asc())
        )

        notes = list(result.scalars().all())

        for index, note in enumerate(notes, start=1):
            note.user_note_number = index

        await self.db.commit()


    async def get_next_user_note_number(self, user_id: int) -> int:
        result = await self.db.execute(
            select(func.max(Note.user_note_number)).where(Note.user_id == user_id)
        )
        max_number = result.scalar_one_or_none()
        return (max_number or 0) + 1