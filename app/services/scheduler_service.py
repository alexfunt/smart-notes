import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

from telegram import Bot

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.repositories.note_repo import NoteRepository
from app.repositories.task_repo import TaskRepository
from app.repositories.user_repo import UserRepository
from app.services.task_engagement import reminder_delta_for_engagement
from app.utils.task_message_templates import random_overdue_text, random_reminder_text

logger = logging.getLogger(__name__)


async def _pause_before_same_chat_reminder(prev_chat_id: int | None, chat_id: int) -> None:
    if (
        prev_chat_id is not None
        and chat_id == prev_chat_id
        and settings.REMINDER_STAGGER_SECONDS > 0
    ):
        await asyncio.sleep(settings.REMINDER_STAGGER_SECONDS)


def _next_check_with_jitter(engagement: float, base_now: datetime) -> datetime:
    delta = reminder_delta_for_engagement(float(engagement))
    jitter = 0
    mx = settings.REMINDER_NEXT_CHECK_JITTER_MAX_SECONDS
    if mx > 0:
        jitter = random.randint(0, mx)
    return base_now + delta + timedelta(seconds=jitter)


async def _resolve_telegram_user(user_repo: UserRepository, task) -> tuple[object, int] | None:
    user = await user_repo.get_by_id(task.user_id)
    if not user:
        logger.warning(
            "skip: no user row for task_id=%s user_id=%s",
            task.id,
            task.user_id,
        )
        return None
    if user.telegram_id is None:
        logger.warning(
            "skip: user id=%s has no telegram_id (task_id=%s)",
            user.id,
            task.id,
        )
        return None
    return user, user.telegram_id


async def check_tasks() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN is empty; skip check_tasks")
        return

    logger.info("CHECK TASK START")
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as db:
        task_repo = TaskRepository(db)
        user_repo = UserRepository(db)
        note_repo = NoteRepository(db)

        overdue_tasks = await task_repo.get_tasks_for_overdue_escalation(now)
        logger.info("FOUND OVERDUE (final notice): %s", len(overdue_tasks))

        regular_tasks = await task_repo.get_tasks_for_check(now)
        logger.info(
            "FOUND TASKS (regular): %s (TASK_REMINDER_INTERVAL_MINUTES=%s)",
            len(regular_tasks),
            settings.TASK_REMINDER_INTERVAL_MINUTES,
        )

        if not overdue_tasks and not regular_tasks:
            logger.info("CHECK TASK END")
            return

        async with Bot(token=settings.TELEGRAM_BOT_TOKEN) as bot:
            prev_overdue_chat: int | None = None
            for task in overdue_tasks:
                resolved = await _resolve_telegram_user(user_repo, task)
                if not resolved:
                    continue
                _, chat_id = resolved
                await _pause_before_same_chat_reminder(prev_overdue_chat, chat_id)
                try:
                    note_title = None
                    if task.note_id:
                        n = await note_repo.get_by_id(task.note_id)
                        if n:
                            note_title = n.title
                    text = random_overdue_text(task.title, note_title)
                    sent = await bot.send_message(chat_id=chat_id, text=text)
                    await task_repo.mark_overdue_escalation_sent(
                        task, now, sent.message_id
                    )
                    logger.info(
                        "overdue notice sent task_id=%s chat_id=%s",
                        task.id,
                        chat_id,
                    )
                    prev_overdue_chat = chat_id
                except Exception:
                    logger.exception(
                        "OVERDUE SEND ERROR task_id=%s chat_id=%s",
                        task.id,
                        chat_id,
                    )

            regular_sorted = sorted(
                regular_tasks,
                key=lambda t: float(t.engagement_score),
                reverse=True,
            )
            prev_regular_chat: int | None = None
            for task in regular_sorted:
                resolved = await _resolve_telegram_user(user_repo, task)
                if not resolved:
                    continue
                _, chat_id = resolved
                await _pause_before_same_chat_reminder(prev_regular_chat, chat_id)
                try:
                    await task_repo.maybe_apply_silent_reminder_penalty(task, now)
                    note_title = None
                    if task.note_id:
                        n = await note_repo.get_by_id(task.note_id)
                        if n:
                            note_title = n.title
                    text = random_reminder_text(task.title, note_title)
                    sent = await bot.send_message(chat_id=chat_id, text=text)
                    await db.refresh(task)
                    send_moment = datetime.now(timezone.utc)
                    task.next_check_at = _next_check_with_jitter(
                        float(task.engagement_score), send_moment
                    )
                    task.last_reminder_telegram_message_id = sent.message_id
                    task.last_reminder_sent_at = send_moment
                    await db.commit()
                    logger.info(
                        "reminder sent task_id=%s user_id=%s chat_id=%s",
                        task.id,
                        task.user_id,
                        chat_id,
                    )
                    prev_regular_chat = chat_id
                except Exception:
                    logger.exception(
                        "SEND ERROR task_id=%s user_id=%s chat_id=%s",
                        task.id,
                        task.user_id,
                        chat_id,
                    )

    logger.info("CHECK TASK END")
