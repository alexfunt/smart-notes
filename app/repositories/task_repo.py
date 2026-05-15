from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, cast, delete, func, literal, or_, select
from sqlalchemy.types import Date as SQLDate
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate
from app.services.task_engagement import reminder_delta_for_engagement


class TaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: TaskCreate) -> Task:
        payload = data.model_dump()
        now = datetime.now(timezone.utc)

        if "user_task_number" not in payload or payload["user_task_number"] is None:
            payload["user_task_number"] = await self.get_next_user_task_number(payload["user_id"])

        payload.setdefault("last_user_engagement_at", now)
        payload.setdefault("engagement_score", 0.5)

        if payload.get("next_check_at") is None:
            eng = float(payload.get("engagement_score", 0.5))
            payload["next_check_at"] = now + reminder_delta_for_engagement(eng)

        task = Task(**payload)
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def get_all(self) -> list[Task]:
        result = await self.db.execute(
            select(Task).order_by(Task.id.desc())
        )
        return list(result.scalars().all())

    async def get_all_by_note_id(self, note_id: int) -> list[Task]:
        result = await self.db.execute(
            select(Task)
            .where(Task.note_id == note_id)
            .order_by(
                case(
                    (Task.status == "pending", 0),
                    (Task.status == "done", 1),
                    else_=2,
                ),
                Task.user_task_number.asc(),
            )
        )
        return list(result.scalars().all())
    
    async def get_all_by_user_id(self, user_id: int) -> list[Task]:
        result = await self.db.execute(
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(
                case(
                    (Task.status == "pending", 0),
                    (Task.status == "done", 1),
                    else_=2,
                ),
                Task.engagement_score.desc(),
                Task.user_task_number.asc(),
            )
        )
        return list(result.scalars().all())

    async def get_by_user_task_number(self, user_id: int, user_task_number: int) -> Task | None:
        result = await self.db.execute(
            select(Task).where(
                Task.user_id == user_id,
                Task.user_task_number == user_task_number,
            )
        )
        return result.scalar_one_or_none()

    async def get_tasks_for_check(self, now: datetime) -> list[Task]:
        """Невыполненные, без финального просроченного уведомления; не в «ожидании» одноразового overdue."""
        interval = settings.task_reminder_delta()
        first_reminder_cutoff = now - interval
        today = literal(now.date(), type_=SQLDate())
        not_waiting_overdue_shot = or_(
            Task.due_date.is_(None),
            cast(Task.due_date, SQLDate) >= today,
        )
        result = await self.db.execute(
            select(Task).where(
                Task.status != "done",
                Task.overdue_escalation_sent_at.is_(None),
                not_waiting_overdue_shot,
                or_(
                    and_(Task.next_check_at.is_not(None), Task.next_check_at <= now),
                    and_(Task.next_check_at.is_(None), Task.created_at <= first_reminder_cutoff),
                ),
            )
        )
        return list(result.scalars().all())

    async def get_tasks_for_overdue_escalation(self, now: datetime) -> list[Task]:
        """Срок по календарной дате уже прошёл (сегодня строго после дня due_date), финальное уведомление ещё не слали."""
        today = literal(now.date(), type_=SQLDate())
        result = await self.db.execute(
            select(Task).where(
                Task.status != "done",
                Task.due_date.is_not(None),
                Task.overdue_escalation_sent_at.is_(None),
                cast(Task.due_date, SQLDate) < today,
            )
        )
        return list(result.scalars().all())

    async def get_by_id(self, task_id: int) -> Task | None:
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()

    async def get_by_user_and_reminder_message_id(
        self, user_id: int, telegram_message_id: int
    ) -> Task | None:
        result = await self.db.execute(
            select(Task).where(
                Task.user_id == user_id,
                Task.last_reminder_telegram_message_id == telegram_message_id,
                Task.status != "done",
            )
        )
        return result.scalar_one_or_none()

    async def append_reminder_reply(self, task: Task, text: str) -> Task:
        block = f"\n\n[Ответ на напоминание]\n{text.strip()}"
        task.description = (task.description or "").rstrip() + block
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def apply_engagement_after_reminder_reply(
        self, task: Task, reply_text: str, now: datetime
    ) -> Task:
        from app.services.task_engagement import (
            blend_engagement_with_history,
            engagement_to_priority,
            score_reminder_reply,
        )

        new = await score_reminder_reply(reply_text, task.due_date, now)
        blended = blend_engagement_with_history(task.engagement_score, new)
        task.engagement_score = blended
        task.priority = engagement_to_priority(blended)
        task.last_user_engagement_at = now
        task.last_reminder_reply_at = now
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def maybe_apply_silent_reminder_penalty(self, task: Task, now: datetime) -> None:
        from app.services.task_engagement import engagement_to_priority

        if task.last_reminder_sent_at is None:
            return
        if task.last_user_engagement_at >= task.last_reminder_sent_at:
            return
        task.engagement_score = max(0.03, task.engagement_score - 0.11)
        task.priority = engagement_to_priority(task.engagement_score)
        await self.db.commit()
        await self.db.refresh(task)

    async def mark_done_from_reminder_reply(self, task: Task) -> Task:
        now = datetime.now(timezone.utc)
        task.status = "done"
        task.next_check_at = None
        task.last_reminder_telegram_message_id = None
        task.engagement_score = max(task.engagement_score, 0.96)
        task.priority = "high"
        task.last_user_engagement_at = now
        task.last_reminder_reply_at = now
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def mark_overdue_escalation_sent(
        self, task: Task, sent_at: datetime, telegram_message_id: int
    ) -> Task:
        task.overdue_escalation_sent_at = sent_at
        task.next_check_at = None
        task.last_reminder_telegram_message_id = telegram_message_id
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def update(self, task: Task, data: TaskUpdate) -> Task:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(task, field, value)

        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def delete(self, task: Task) -> None:
        user_id = task.user_id
        note_id = task.note_id

        await self.db.delete(task)
        await self.db.commit()

        await self.reorder_user_tasks(user_id, note_id)

    async def delete_by_note_id(self, note_id: int) -> None:
        await self.db.execute(
            delete(Task).where(Task.note_id == note_id)
        )
        await self.db.commit()

    async def get_next_user_task_number(self, user_id: int) -> int:
        result = await self.db.execute(
            select(func.max(Task.user_task_number)).where(Task.user_id == user_id)
        )
        max_number = result.scalar_one_or_none()
        return (max_number or 0) + 1

    async def reorder_user_tasks(self, user_id: int, note_id: int) -> None:
        if note_id is None:
            return

        result = await self.db.execute(
            select(Task)
            .where(Task.user_id == user_id, Task.note_id == note_id)
            .order_by(Task.created_at.asc(), Task.id.asc())
        )
        tasks = list(result.scalars().all())

        for index, task in enumerate(tasks, start=1):
            task.user_task_number = index

        await self.db.commit()

    async def get_by_id_and_user_id(self, task_id: int, user_id: int) -> Task | None:
        result = await self.db.execute(
            select(Task).where(
                Task.id == task_id,
                Task.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def toggle_status(self, task: Task) -> Task:
        from app.services.task_engagement import engagement_to_priority

        now = datetime.now(timezone.utc)
        task.last_user_engagement_at = now
        was_pending = task.status == "pending"
        task.status = "done" if was_pending else "pending"
        if was_pending:
            task.engagement_score = max(task.engagement_score, 0.88)
            task.priority = "high"
        else:
            task.priority = engagement_to_priority(task.engagement_score)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    