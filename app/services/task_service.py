from app.repositories.task_repo import TaskRepository
from app.schemas.task import TaskCreate, TaskUpdate


class TaskService:
    def __init__(self, repo: TaskRepository):
        self.repo = repo

    async def create_task(self, data: TaskCreate):
        return await self.repo.create(data)

    async def get_tasks(self):
        return await self.repo.get_all()

    async def get_task(self, task_id: int):
        return await self.repo.get_by_id(task_id)

    async def update_task(self, task_id: int, data: TaskUpdate):
        task = await self.repo.get_by_id(task_id)
        if not task:
            return None
        return await self.repo.update(task, data)

    async def delete_task(self, task_id: int):
        task = await self.repo.get_by_id(task_id)
        if not task:
            return False
        await self.repo.delete(task)
        return True