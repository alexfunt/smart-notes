from datetime import date, datetime, timezone

from app.repositories.note_repo import NoteRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.user_repo import UserRepository
from app.utils.task_reminder_intent import is_task_done_acknowledgment
from app.schemas.note import NoteCreate, NoteUpdate
from app.schemas.task import TaskCreate
from app.schemas.telegram import TelegramAuthRequest, TelegramWebhookRequest
from app.schemas.user import UserCreate
from app.services.note_focus import FocusEvent


def _parse_due_date_text(due_date_text: str | None) -> datetime | None:
    if not due_date_text:
        return None
    raw = due_date_text.strip()[:10]
    try:
        d = date.fromisoformat(raw)
        return datetime(d.year, d.month, d.day, 12, 0, tzinfo=timezone.utc)
    except ValueError:
        return None


class TelegramService:
    def __init__(
        self,
        note_repo: NoteRepository,
        user_repo: UserRepository,
        task_repo: TaskRepository,
    ):
        self.note_repo = note_repo
        self.user_repo = user_repo
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

    async def auth_telegram_webapp(self, init_data: str):
        """Проверяет initData (HMAC от bot_token) и возвращает пользователя.

        Поднимает app.utils.telegram_webapp.WebAppAuthError при невалидной подписи.
        """
        from app.core.config import settings
        from app.utils.telegram_webapp import verify_init_data

        auth = verify_init_data(
            init_data,
            settings.TELEGRAM_BOT_TOKEN,
            max_age_seconds=settings.WEBAPP_INITDATA_MAX_AGE,
        )
        full_name = " ".join(
            part for part in [auth.user.first_name, auth.user.last_name] if part
        ).strip() or None
        return await self.get_or_create_user(
            telegram_id=auth.user.id,
            username=auth.user.username,
            full_name=full_name,
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

        if message.reply_to_message:
            task = await self.task_repo.get_by_user_and_reminder_message_id(
                user.id, message.reply_to_message.message_id
            )
            if task:
                if is_task_done_acknowledgment(message.text):
                    await self.task_repo.mark_done_from_reminder_reply(task)
                    now = datetime.now(timezone.utc)
                    if task.note_id:
                        n = await self.note_repo.get_by_id(task.note_id)
                        if n:
                            await self.note_repo.apply_focus_event(
                                n, FocusEvent.TASK_DONE, now
                            )
                    return {
                        "status": "ok",
                        "kind": "task_reminder_done",
                        "task_id": task.id,
                        "user_task_number": task.user_task_number,
                        "task_title": task.title,
                        "message": "Task marked done from reminder reply",
                    }
                await self.task_repo.append_reminder_reply(task, message.text)
                now = datetime.now(timezone.utc)
                await self.task_repo.apply_engagement_after_reminder_reply(
                    task, message.text, now
                )
                if task.note_id:
                    n = await self.note_repo.get_by_id(task.note_id)
                    if n:
                        await self.note_repo.apply_focus_event(
                            n, FocusEvent.REMINDER_REPLY, now
                        )
                return {
                    "status": "ok",
                    "kind": "task_reminder_reply",
                    "task_id": task.id,
                    "user_task_number": task.user_task_number,
                    "task_title": task.title,
                    "message": "Reply saved on task",
                }

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
        now = datetime.now(timezone.utc)
        await self.note_repo.apply_focus_event(note, FocusEvent.NEW_NOTE, now)

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

    async def get_user_tasks(self, telegram_id: int):
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return []
        return await self.task_repo.get_all_by_user_id(user.id)

    async def get_user_note_details(
        self,
        telegram_id: int,
        user_note_number: int,
        focus: str | None = None,
    ):
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return None

        note = await self.note_repo.get_by_user_note_number(user.id, user_note_number)
        if not note:
            return None

        now = datetime.now(timezone.utc)
        if focus == "note":
            note = await self.note_repo.apply_focus_event(
                note, FocusEvent.NOTE_OPEN, now
            )
        elif focus == "task":
            note = await self.note_repo.apply_focus_event(
                note, FocusEvent.TASK_OPEN, now
            )

        tasks = await self.task_repo.get_all_by_note_id(note.id)
        return note, tasks

    async def update_user_note(
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

    async def delete_user_note(self, telegram_id: int, user_note_number: int) -> bool:
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return False

        note = await self.note_repo.get_by_user_note_number(user.id, user_note_number)
        if not note:
            return False

        tasks = await self.task_repo.get_all_by_note_id(note.id)
        if tasks:
            await self.task_repo.delete_by_note_id(note.id)

        await self.note_repo.delete(note)
        return True

    async def create_task_from_note(
        self,
        telegram_id: int,
        user_note_number: int,
        title: str,
        description: str | None,
        due_date_text: str | None,
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

        due_dt = _parse_due_date_text(due_date_text)

        task = await self.task_repo.create(
            TaskCreate(
                user_id=user.id,
                note_id=note.id,
                title=title[:255],
                description=full_description,
                priority="medium",
                status="pending",
                due_date=due_dt,
                ai_generated=False,
                user_task_number=None,
            )
        )

        now = datetime.now(timezone.utc)
        await self.note_repo.apply_focus_event(note, FocusEvent.TASK_CREATED, now)

        return task

    async def toggle_task_status(self, telegram_id: int, task_id: int):
        user = await self.user_repo.get_by_telegram_id(telegram_id)

        if not user:
            return None

        task = await self.task_repo.get_by_id_and_user_id(task_id, user.id)

        if not task:
            return None

        was_pending = task.status == "pending"
        task = await self.task_repo.toggle_status(task)
        now = datetime.now(timezone.utc)
        if was_pending and task.status == "done" and task.note_id:
            n = await self.note_repo.get_by_id(task.note_id)
            if n:
                await self.note_repo.apply_focus_event(n, FocusEvent.TASK_DONE, now)
        return task

    async def delete_user_task(self, telegram_id: int, task_id: int) -> bool:
        user = await self.user_repo.get_by_telegram_id(telegram_id)
        if not user:
            return False
        task = await self.task_repo.get_by_id_and_user_id(task_id, user.id)
        if not task:
            return False
        await self.task_repo.delete(task)
        return True