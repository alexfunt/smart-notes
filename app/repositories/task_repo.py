from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.task import Task
from app.schemas.task import TaskCreate, TaskUpdate


class TaskRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_next_user_task_number(self, user_id: int) -> int:
        result = await self.db.execute(
            select(func.max(Task.user_task_number)).where(Task.user_id == user_id)
        )
        max_number = result.scalar_one_or_none()
        return (max_number or 0) + 1

    async def create(self, data: TaskCreate) -> Task:
        payload = data.model_dump()

        if "user_task_number" not in payload or payload["user_task_number"] is None:
            payload["user_task_number"] = await self.get_next_user_task_number(payload["user_id"])
        
        task = Task(**payload)
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def get_all_by_note_id(self, note_id: int) -> list[Task]:
        result = await self.db.execute(
            select(Task)
            .where(Task.note_id == note_id)
            .order_by(Task.user_task_number.asc())
        )
        return list(result.scalars().all())
    
    async def get_all_by_user_id(self, user_id: int) -> list[Task]:
        result = await self.db.execute(
            select(Task)
            .where(Task.user_id == user_id)
            .order_by(Task.user_task_number.asc())
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

    async def get_by_id(self, task_id: int) -> Task | None:
        result = await self.db.execute(select(Task).where(Task.id == task_id))
        return result.scalar_one_or_none()

    async def update(self, task: Task, data: TaskUpdate) -> Task:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(task, field, value)

        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def delete(self, task: Task) -> None:
        await self.db.delete(task)
        await self.db.commit()
    
    