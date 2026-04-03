from app.repositories.note_repo import NoteRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.user_repo import UserRepository
from app.schemas.note import NoteCreate, NoteUpdate


class NoteService:
    def __init__(self, user_repo: UserRepository, note_repo: NoteRepository, task_repo: TaskRepository):
        self.user_repo = user_repo,
        self.note_repo = note_repo,
        self.task_repo = task_repo

    async def create_note(self, data: NoteCreate):
        return await self.repo.create(data)

    async def get_notes(self):
        return await self.repo.get_all()

    async def get_note(self, note_id: int):
        return await self.repo.get_by_id(note_id)

    async def update_note(
        self, 
        telegram_id: int,
        user_note_number: int, 
        new_content: str,
        ):
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return None
        
        note = await self.note_repo.get_by_user_note_number(user.id, user_note_number)
        if not note:
            return None
        return await self.note_repo.update(
            note,
            NoteUpdate(
                title=self._build_note_title(new_content),
                content=new_content,
            ),
        )

    async def delete_by_id(self, note_id: int) -> bool:
        note = await self.note_repo.get_by_id(note_id)
        if not note:
            return False

        await self.note_repo.delete(note)
        return True

    async def get_by_user_id(self, user_id: int):
        return await self.note_repo.get_all_by_user_id(user_id)

    async def delete_by_user_note_number(self, telegram_id: int, user_note_number: int) -> bool:
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return False

        note = await self.note_repo.get_by_user_note_number(user.id, user_note_number)
        if not note:
            return False

        await self.note_repo.delete(note)
        return True