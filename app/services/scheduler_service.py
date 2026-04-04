import logging
from datetime import datetime, timezone

from telegram import Bot

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.repositories.task_repo import TaskRepository
from app.repositories.user_repo import UserRepository
from app.utils.task_message_templates import random_overdue_text, random_reminder_text

logger = logging.getLogger(__name__)


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
            for task in overdue_tasks:
                resolved = await _resolve_telegram_user(user_repo, task)
                if not resolved:
                    continue
                _, chat_id = resolved
                try:
                    text = random_overdue_text(task.title)
                    sent = await bot.send_message(chat_id=chat_id, text=text)
                    await task_repo.mark_overdue_escalation_sent(
                        task, now, sent.message_id
                    )
                    logger.info(
                        "overdue notice sent task_id=%s chat_id=%s",
                        task.id,
                        chat_id,
                    )
                except Exception:
                    logger.exception(
                        "OVERDUE SEND ERROR task_id=%s chat_id=%s",
                        task.id,
                        chat_id,
                    )

            for task in regular_tasks:
                resolved = await _resolve_telegram_user(user_repo, task)
                if not resolved:
                    continue
                _, chat_id = resolved
                try:
                    await task_repo.maybe_apply_silent_reminder_penalty(task, now)
                    text = random_reminder_text(task.title)
                    sent = await bot.send_message(chat_id=chat_id, text=text)
                    task.next_check_at = now + settings.task_reminder_delta()
                    task.last_reminder_telegram_message_id = sent.message_id
                    task.last_reminder_sent_at = now
                    await db.commit()
                    logger.info(
                        "reminder sent task_id=%s user_id=%s chat_id=%s",
                        task.id,
                        task.user_id,
                        chat_id,
                    )
                except Exception:
                    logger.exception(
                        "SEND ERROR task_id=%s user_id=%s chat_id=%s",
                        task.id,
                        task.user_id,
                        chat_id,
                    )

    logger.info("CHECK TASK END")
