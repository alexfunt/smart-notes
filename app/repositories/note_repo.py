from datetime import datetime

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.note import Note
from app.models.task import Task
from app.schemas.note import NoteCreate, NoteUpdate
from app.services.note_focus import FocusEvent


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

    async def get_all_by_user_id(self, user_id: int) -> list[Note]:
        """Сортировка: активные темы выше — по задачам, ответам и фокусу (без LLM)."""
        task_agg = (
            select(
                Task.note_id.label("nid"),
                func.count(Task.id).label("task_cnt"),
                func.avg(Task.engagement_score).label("avg_eng"),
                func.sum(case((Task.status == "done", 1), else_=0)).label("done_cnt"),
            )
            .where(Task.note_id.isnot(None))
            .group_by(Task.note_id)
        ).subquery()

        list_rank = (
            Note.focus_score * 0.30
            + func.coalesce(task_agg.c.avg_eng, 0.5) * 0.42
            + func.least(func.coalesce(task_agg.c.task_cnt, 0) / 8.0, 1.0) * 0.16
            + func.least(func.coalesce(task_agg.c.done_cnt, 0) / 5.0, 1.0) * 0.12
        )

        result = await self.db.execute(
            select(Note)
            .outerjoin(task_agg, Note.id == task_agg.c.nid)
            .where(Note.user_id == user_id)
            .order_by(list_rank.desc(), Note.updated_at.desc())
        )
        return list(result.scalars().all())

    async def apply_focus_event(
        self, note: Note, event: FocusEvent, now: datetime
    ) -> Note:
        from app.services.note_focus import apply_focus_delta

        new_score, new_at = apply_focus_delta(
            note.focus_score, note.last_focus_at, now, event
        )
        note.focus_score = new_score
        note.last_focus_at = new_at
        await self.db.commit()
        await self.db.refresh(note)
        return note

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