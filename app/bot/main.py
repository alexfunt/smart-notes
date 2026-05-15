from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.bot.handlers import (
    app_command,
    help_command,
    note_action_callback,
    note_command,
    notes_command,
    open_app_callback,
    start_command,
    task_from_note_command,
    text_message_handler,
    open_note_callback,
    delete_note_callback,
    confirm_delete_note_callback,
    edit_note_callback,
    open_task_callback,
    delete_task_callback,
    confirm_delete_task_callback,
    back_to_notes_callback,
    cancel_task_creation_callback,
    toggle_task_callback,
)
from app.core.config import settings

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.scheduler_service import check_tasks


def main() -> None:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN is empty in .env")

    application = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("app", app_command))
    application.add_handler(CommandHandler("notes", notes_command))
    application.add_handler(CommandHandler("note", note_command))
    application.add_handler(CommandHandler("taskfromnote", task_from_note_command))

    application.add_handler(CallbackQueryHandler(confirm_delete_note_callback, pattern=r"^confirm_delete_note:"))
    application.add_handler(CallbackQueryHandler(open_note_callback, pattern=r"^open_note:"))
    application.add_handler(CallbackQueryHandler(delete_note_callback, pattern=r"^delete_note:"))
    application.add_handler(CallbackQueryHandler(edit_note_callback, pattern=r"^edit_note:"))
    application.add_handler(
        CallbackQueryHandler(confirm_delete_task_callback, pattern=r"^confirm_delete_task:")
    )
    application.add_handler(CallbackQueryHandler(delete_task_callback, pattern=r"^delete_task:"))
    application.add_handler(CallbackQueryHandler(open_task_callback, pattern=r"^open_task:"))
    application.add_handler(CallbackQueryHandler(back_to_notes_callback, pattern=r"^back_to_notes$"))
    application.add_handler(CallbackQueryHandler(note_action_callback, pattern=r"^(create_task|later):"))
    application.add_handler(CallbackQueryHandler(toggle_task_callback, pattern=r"^toggle_task:"))
    application.add_handler(CallbackQueryHandler(open_app_callback, pattern=r"^open_app$"))

    application.add_handler(CallbackQueryHandler(cancel_task_creation_callback, pattern=r"^cancel_task_creation:"))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_message_handler))

    print("Telegram bot is running...")
    application.run_polling()


if __name__ == "__main__":
    main()