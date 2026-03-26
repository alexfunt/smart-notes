from app.repositories.note_repo import NoteRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.user_repo import UserRepository
from app.schemas.note import NoteCreate, NoteUpdate
from app.schemas.task import TaskCreate
from app.schemas.telegram import TelegramAuthRequest, TelegramWebhookRequest
from app.schemas.user import UserCreate

class TelegramService:
    def __init__(
        self,
        user_repo: UserRepository,
        note_repo: NoteRepository,
        task_repo: TaskRepository,
    ):
        self.user_repo = user_repo
        self.note_repo = note_repo
        self.task_repo = task_repo

    @staticmethod
    def _build_note_title(text: str) -> str:
        clean = text.strip().replace("\n", " ")
        if not clean:
            return "Telegram note"
        return clean[:40] + ("..." if len(clean) > 40 else "")

    async def get_or_create_user(
        self,
        telegram_id: int,
        username: str | None = None,
        full_name: str | None = None,
    ):
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if user:
            return user

        return await self.user_repo.create(
            UserCreate(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                email=None,
                timezone="UTC",
            )
        )

    async def auth_telegram_user(self, data: TelegramAuthRequest):
        return await self.get_or_create_user(
            telegram_id=data.telegram_id,
            username=data.username,
            full_name=data.full_name,
        )

    async def handle_webhook(self, payload: TelegramWebhookRequest) -> dict:
        if not payload.message:
            return {"status": "ignored", "reason": "no_message"}

        message = payload.message

        if not message.text:
            return {"status": "ignored", "reason": "no_text"}

        tg_user = message.from_user
        full_name = " ".join(
            part for part in [tg_user.first_name, tg_user.last_name] if part
        ).strip() or None

        user = await self.get_or_create_user(
            telegram_id=tg_user.id,
            username=tg_user.username,
            full_name=full_name,
        )

        note = await self.note_repo.create(
            NoteCreate(
                user_id=user.id,
                title=self._build_note_title(message.text),
                content=message.text,
                source="telegram",
                note_type="plain",
                status="active",
                metadata_json={
                    "chat_id": message.chat.id,
                    "message_id": message.message_id,
                    "update_id": payload.update_id,
                },
            )
        )

        return {
            "status": "ok",
            "user_id": user.id,
            "note_id": note.id,
            "user_note_number": note.user_note_number,
            "message": "Telegram message saved as note",
        }


    async def get_user_notes(self, telegram_id: int):
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return []
        return await self.note_repo.get_all_by_user_id(user.id)

    async def update_user_note(
        self,
        telegram_id: int,
        note_id: int,
        new_content: str,
    ):
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return None

        note = await self.note_repo.get_by_id_and_user_id(note_id, user.id)
        if not note:
            return None

        return await self.note_repo.update(
            note,
            NoteUpdate(
                title=self._build_note_title(new_content),
                content=new_content,
            ),
        )

    async def delete_user_note(self, telegram_id: int, note_id: int) -> bool:
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return False

        note = await self.note_repo.get_by_id_and_user_id(note_id, user.id)
        if not note:
            return False

        await self.note_repo.delete(note)
        return True

    async def get_user_note_details(self, telegram_id: int, user_note_number: int):
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return None

        note = await self.note_repo.get_by_user_note_number(user.id, user_note_number)
        if not note:
            return None

        tasks = await self.task_repo.get_all_by_note_id(note.id)
        return note, tasks

    async def create_task_from_note(
        self,
        telegram_id: int,
        user_note_number: int,
        title: str,
        description: str | None,
        due_date_text: str | None,
        priority: str,
    ):
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return None

        note = await self.note_repo.get_by_user_note_number(user.id, user_note_number)
        if not note:
            return None

        full_description = description or ""
        if due_date_text:
            full_description = f"{full_description}\nСрок: {due_date_text}".strip()

        task = await self.task_repo.create(
            TaskCreate(
                user_id=user.id,
                note_id=note.id,
                title=title[:255],
                description=full_description,
                priority=priority,
                status="pending",
                due_date=None,
                ai_generated=False,
                user_task_number=None,
            )
        )

        return task