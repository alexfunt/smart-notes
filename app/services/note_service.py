from app.schemas.note import NoteCreate, NoteUpdate


class NoteService:
    def __init__(self, note_repo, user_repo, task_repo):
        self.note_repo = note_repo
        self.user_repo = user_repo
        self.task_repo = task_repo

    async def create_note(self, data: NoteCreate):
        return await self.note_repo.create(data)

    async def get_notes(self):
        return await self.note_repo.get_all()

    async def get_note(self, note_id: int):
        return await self.note_repo.get_by_id(note_id)

    async def update_note(self, note_id: int, data: NoteUpdate):
        note = await self.note_repo.get_by_id(note_id)
        if not note:
            return None
        return await self.note_repo.update(note, data)

    async def delete_by_id(self, note_id: int) -> bool:
        note = await self.note_repo.get_by_id(note_id)
        if not note:
            return False

        tasks = await self.task_repo.get_all_by_note_id(note.id)
        if tasks:
            await self.task_repo.delete_by_note_id(note.id)

        await self.note_repo.delete(note)
        return True