import httpx

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from app.bot.utils import parse_task_template

from app.bot.client import BackendClient

client = BackendClient()


async def _safe_backend_error(message, error: Exception) -> None:
    if isinstance(error, httpx.ConnectError):
        await message.reply_text(
            "Сервис временно недоступен. Попробуйте еще раз через минуту."
        )
        return

    await message.reply_text("Произошла ошибка при обращении к серверу.")

def format_task_status(status: str) -> str:
    mapping = {
        "pending" : "ожидает выполнения",
        "in_progress" : "в процессе",
        "done" :  "выполнена",
    }
    return mapping.get(status, status)

def format_task_priority(priority: str) -> str:
    mapping = {
        "low" : "низкий",
        "medium" : "средний",
        "high" : "высокий",
    }
    return mapping.get(priority, priority)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user or not update.message:
        return

    full_name = " ".join(
        part for part in [user.first_name, user.last_name] if part
    ).strip() or None

    try:
        await client.auth_telegram_user(
            telegram_id=user.id,
            username=user.username,
            full_name=full_name,
        )

        await update.message.reply_text(
            "Привет! Я бот для smart-заметок.\n\n"
            "Что я умею сейчас:\n"
            "/notes — показать мои заметки\n"
            "/edit <id> новый текст — изменить заметку\n"
            "/delete <id> — удалить заметку\n"
            "/help — помощь\n\n"
            "Просто пришли мне текст, и я сохраню его как заметку."
        )
    except Exception as e:
        await _safe_backend_error(update.message, e)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    await update.message.reply_text(
        "Доступные команды:\n"
        "/start — старт\n"
        "/help — помощь\n"
        "/notes — мои заметки\n"
        "/edit <id> новый текст — изменить заметку\n"
        "/delete <id> — удалить заметку\n\n"
        "Также можно просто отправить текстовое сообщение — оно сохранится как заметка."
    )


async def notes_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not update.message or not user:
        return

    try:
        notes = await client.get_user_notes(user.id)

        if not notes:
            await update.message.reply_text("У вас пока нет заметок.")
            return

        keyboard=[]    
        for note in notes[:10]:
            preview = note["content"][:35].replace("\n", " ")
            if len(note["content"]) > 35:
                preview += "..."
            keyboard.append([
                InlineKeyboardButton(
                    f"#{note['user_note_number']} — {preview}",
                    callback_data=f"open_note:{note['user_note_number']}",
                )
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Ваши заметки:",
            reply_markup=reply_markup,
        )
    except Exception as e:
        await _safe_backend_error(update.message, e)

async def open_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    await query.answer()

    data = query.data or ""
    if not data.startswith("open_task:"):
        return

    try:
        _, note_number_str, task_number_str = data.split(":")
        note_number = int(note_number_str)
        task_number = int(task_number_str)
    except (ValueError, IndexError):
        await query.edit_message_text("Некорректные параметры задачи.")
        return

    user = update.effective_user
    if not user:
        return

    try:
        note = await client.get_user_note_details(user.id, note_number)
    except Exception as e:
        await _safe_backend_error(query.message, e)
        return

    task = None
    for item in note.get("tasks", []):
        if item["user_task_number"] == task_number:
            task = item
            break

    if not task:
        await query.edit_message_text("Задача не найдена.")
        return

    description = task.get("description") or "Нет описания"
    status_text = "выполнена" if task["status"] == "done" else "не выполнена"
    button_text = "↩ Снять выполнение" if task["status"] == "done" else "✅ Отметить выполненной"

    eng = float(task.get("engagement_score", 0.5))
    text = (
        f"Задача #{task['user_task_number']}\n\n"
        f"Название: {task['title']}\n"
        f"Описание: {description}\n"
        f"Состояние: {status_text}\n"
        f"Приоритет: {format_task_priority(task['priority'])} "
        f"(вовлечённость {eng:.2f}, обновляется по ответам)"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    button_text,
                    callback_data=f"toggle_task:{note_number}:{task['id']}",
                )
            ],
            [
                InlineKeyboardButton(
                    "Назад к заметке",
                    callback_data=f"open_note:{note_number}",
                )
            ]
        ]
    )

    await query.edit_message_text(text, reply_markup=keyboard)

async def show_note(update, context, note_number: int):
    query = update.callback_query
    user = update.effective_user

    try:
        note = await client.get_user_note_details(user.id, note_number)
    except Exception as e:
        await _safe_backend_error(query.message, e)
        return

    lines = [
        f"Заметка #{note['user_note_number']}",
        "",
        f"{note['content']}",
        "",
        "Связанные задачи:"
    ]

    keyboard = []

    tasks = note.get("tasks", [])
    if not tasks:
        lines.append("Пока нет задач.")
    else:
        for task in tasks:
            status_icon = "✅" if task["status"] == "done" else "⬜"

            keyboard.append([
                InlineKeyboardButton(
                    status_icon,
                    callback_data=f"toggle_task:{note_number}:{task['id']}",
                ),
                InlineKeyboardButton(
                    f"Задача #{task['user_task_number']} — {task['title']}",
                    callback_data=f"open_task:{note_number}:{task['user_task_number']}",
                )
            ])

    keyboard.append([
        InlineKeyboardButton(
            "➕ Добавить задачу",
            callback_data=f"create_task:{note_number}",
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            "✏️ Редактировать",
            callback_data=f"edit_note:{note_number}",
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            "🗑 Удалить",
            callback_data=f"delete_note:{note_number}",
        )
    ])

    keyboard.append([
        InlineKeyboardButton(
            "Назад к заметкам",
            callback_data="back_to_notes",
        )
    ])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def open_note_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user

    if not query or not user:
        return

    await query.answer()

    data = query.data or ""
    if not data.startswith("open_note:"):
        return

    try:
        note_number = int(data.split(":")[1])
    except (IndexError, ValueError):
        await query.edit_message_text("Некорректный номер заметки.")
        return

    await show_note(update, context, note_number)

async def back_to_notes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user

    if not query or not user:
        return

    await query.answer()

    try:
        notes = await client.get_user_notes(user.id)

        if not notes:
            await query.edit_message_text("У вас пока нет заметок.")
            return

        keyboard = []
        for note in notes[:10]:
            preview = note["content"][:35].replace("\n", " ")
            if len(note["content"]) > 35:
                preview += "..."
            keyboard.append([
                InlineKeyboardButton(
                    f"#{note['user_note_number']} — {preview}",
                    callback_data=f"open_note:{note['user_note_number']}",
                )
            ])

        await query.edit_message_text(
            "Ваши заметки:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
    except Exception as e:
        await _safe_backend_error(query.message, e)

async def note_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user

    if not query or not user:
        return

    await query.answer()

    data = query.data or ""
    if ":" not in data:
        return

    action, value = data.split(":", 1)

    try:
        note_number = int(value)
    except ValueError:
        await query.edit_message_text("Некорректный номер заметки.")
        return

    if action == "create_task":
        context.user_data["task_from_note_number"] = note_number

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "⬅ Назад к заметке",
                        callback_data=f"cancel_task_creation:{note_number}",
                    )
                ]
            ]
        )

        await query.edit_message_text(
            f"Хорошо, оформим задачу для заметки #{note_number}.\n\n"
            "Пришлите данные в формате:\n\n"
            "1 строка — название\n"
            "2 строка — описание\n"
            "3 строка — срок (завтра, сегодня или YYYY-MM-DD)\n\n"
            "Приоритет подставится сам и будет уточняться по твоим ответам на напоминания.\n\n"
            "Пример:\n"
            "Сделать математику\n"
            "Упражнение 2\n"
            "Завтра",
            reply_markup=keyboard,
        )
        return

    if action == "later":
        await query.edit_message_text(
            f"Хорошо, заметка #{note_number} сохранена.\n"
            f"Позже можно вернуться через команду /taskfromnote {note_number}"
        )

async def note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not update.message or not user:
        return

    if not context.args:
        await update.message.reply_text("Использование: /note <номер>")
        return

    try:
        note_number = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Номер заметки должен быть числом.")
        return

    try:
        note = await client.get_user_note_details(user.id, note_number)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            await update.message.reply_text("Заметка не найдена.")
            return
        await _safe_backend_error(update.message, e)
        return
    except Exception as e:
        await _safe_backend_error(update.message, e)
        return

    lines = [
        f"Заметка #{note['user_note_number']}",
        f"Текст: {note['content']}",
        "",
        "Связанные задачи:"
    ]

    tasks = note.get("tasks", [])
    if not tasks:
        lines.append("Пока нет задач.")
    else:
        for task in tasks:
            eng = float(task.get("engagement_score", 0.5))
            lines.append(
                f"• #{task['user_task_number']} — {task['title']} "
                f"[{task['status']}, {task['priority']}, вовл. {eng:.2f}]"
            )

    lines.append("")
    lines.append(f"Добавить задачу: /taskfromnote {note['user_note_number']}")

    await update.message.reply_text("\n".join(lines))

async def delete_note_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user

    if not query or not user:
        return

    await query.answer()

    try:
        note_number = int(query.data.split(":")[1])
    except (IndexError, ValueError):
        await query.edit_message_text("Ошибка номера заметки.")
        return

    try:
        note_data = await client.get_user_note_details(user.id, note_number)
        tasks = note_data.get("tasks", [])

        if not tasks:
            await client.delete_note(
                telegram_id=user.id,
                note_number=note_number,
            )
            await query.edit_message_text(
                f"Заметка #{note_number} удалена.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📒 К заметкам", callback_data="back_to_notes")]]
                ),
            )
            return

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ Удалить заметку и задачи",
                        callback_data=f"confirm_delete_note:{note_number}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        "⬅ Отмена",
                        callback_data=f"open_note:{note_number}",
                    )
                ]
            ]
        )
        await query.edit_message_text(
            f"У заметки #{note_number} есть связанные задачи: {len(tasks)} шт.\n\n"
            "Удалить заметку вместе со всеми задачами?",
            reply_markup=keyboard,
        )

    except httpx.HTTPStatusError as e:
        print("HTTP STATUS ERROR:", e.response.status_code)
        print("RESPONSE TEXT:", e.response.text)

        if e.response.status_code == 404:
            await query.edit_message_text(
                "Заметка не найдена или уже была удалена.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📒 К заметкам", callback_data="back_to_notes")]]
                ),
            )
            return

        await query.edit_message_text(
            "Ошибка сервера при удалении заметки.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("📒 К заметкам", callback_data="back_to_notes")]]
            ),
        )

    except Exception as e:
        print("UNEXPECTED DELETE ERROR:", repr(e))
        await _safe_backend_error(query.message, e)

async def toggle_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user

    if not query or not user:
        return

    await query.answer()

    print("TOGGLE CALLBACK DATA:", query.data)

    try:
        _, note_number_str, task_id_str = query.data.split(":")
        note_number = int(note_number_str)
        task_id = int(task_id_str)
    except (IndexError, ValueError):
        await query.edit_message_text("Некорректные параметры задачи.")
        return

    print("NOTE NUMBER:", note_number)
    print("TASK ID:", task_id)

    try:
        task = await client.toggle_task(user.id, task_id)
        print("TOGGLE RESPONSE:", task)

        await show_note(update, context, note_number)

    except httpx.HTTPStatusError as e:
        print("TOGGLE HTTP STATUS:", e.response.status_code)
        print("TOGGLE RESPONSE:", e.response.text)
        await query.edit_message_text("Ошибка сервера при изменении статуса задачи.")
    except Exception as e:
        print("TOGGLE ERROR:", repr(e))
        await query.edit_message_text(f"Ошибка toggle: {e}")

async def edit_note_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user

    if not query or not user:
        return

    await query.answer()

    try:
        note_number = int(query.data.split(":")[1])
    except:
        await query.edit_message_text("Ошибка номера заметки.")
        return

    context.user_data["edit_note_number"] = note_number

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⬅ Отмена",
                    callback_data=f"open_note:{note_number}",
                )
            ]
        ]
    )

    await query.edit_message_text(
        f"Редактирование заметки #{note_number}\n\n"
        "Пришлите новый текст заметки.",
        reply_markup=keyboard,
    )

async def task_from_note_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    message = update.message

    if not message or not user:
        return

    if not context.args:
        await update.message.reply_text("Использование: /taskfromnote <номер заметки>")
        return

    try:
        note_number = int(context.args[0])
    except ValueError:
        await message.reply_text("Номер заметки должен быть числом.")
        return

    try:
        note = await client.get_user_note_details(user.id, note_number)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            await message.reply_text("Заметка не найдена.")
            return
        await _safe_backend_error(message, e)
        return
    except Exception as e:
        await _safe_backend_error(message, e)
        return

    context.user_data["task_from_note_number"] = note_number

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "⬅ Назад к заметке",
                    callback_data=f"cancel_task_creation:{note_number}",
                )
            ]
        ]
    )

    await message.reply_text(
        f"Вы выбрали заметку #{note_number}:\n"
        f"{note['content'][:150]}\n\n"
        "Теперь пришлите задачу в формате:\n\n"
        "1 строка — название\n"
        "2 строка — описание\n"
        "3 строка — срок (завтра, сегодня или YYYY-MM-DD)\n\n"
        "Приоритет выставится автоматически и обновится по ответам на напоминания.\n\n"
        "Пример:\n"
        "Сделать математику\n"
        "Упражнение 2\n"
        "Завтра",
        reply_markup=keyboard,
    )

async def cancel_task_creation_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user

    if not query or not user:
        return

    await query.answer()

    data = query.data or ""
    if not data.startswith("cancel_task_creation:"):
        return

    try:
        note_number = int(data.split(":")[1])
    except (IndexError, ValueError):
        await query.edit_message_text("Некорректный номер заметки.")
        return

    context.user_data.pop("task_from_note_number", None)

    try:
        note = await client.get_user_note_details(user.id, note_number)
    except Exception as e:
        await _safe_backend_error(query.message, e)
        return

    lines = [
        f"Заметка #{note['user_note_number']}",
        "",
        f"{note['content']}",
        "",
        "Связанные задачи:"
    ]

    keyboard = []

    tasks = note.get("tasks", [])
    if not tasks:
        lines.append("Пока нет задач.")
    else:
        for task in tasks:
            keyboard.append([
                InlineKeyboardButton(
                    f"Задача #{task['user_task_number']} — {task['title']}",
                    callback_data=f"open_task:{note['user_note_number']}:{task['user_task_number']}",
                )
            ])

    keyboard.append([
        InlineKeyboardButton(
            "Добавить задачу",
            callback_data=f"create_task:{note['user_note_number']}",
        )
    ])
    keyboard.append([
        InlineKeyboardButton(
            "Назад к заметкам",
            callback_data="back_to_notes",
        )
    ])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
async def text_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:

    edit_note_number = context.user_data.get("edit_note_number")
    message = update.message
    user = update.effective_user

    if edit_note_number:
        try:
            await client.update_user_note(
                telegram_id=user.id,
                note_number=edit_note_number,
                content=message.text,
            )

            context.user_data.pop("edit_note_number", None)

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "Открыть заметку",
                            callback_data=f"open_note:{edit_note_number}",
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "📒 К заметкам",
                            callback_data="back_to_notes",
                        )
                    ]
                ]
            )

            await message.reply_text(
                f"Заметка #{edit_note_number} обновлена.",
                reply_markup=keyboard,
            )
            return
        except Exception as e:
            await _safe_backend_error(message, e)
            return

    chat = update.effective_chat

    if not message or not user or not chat or not message.text:
        return

    pending_note_number = context.user_data.get("task_from_note_number")
    parsed_task = parse_task_template(message.text)

    
    if pending_note_number:
        if not parsed_task:

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅ Назад к заметке",
                            callback_data=f"cancel_task_creation:{pending_note_number}",
                        )
                    ]
                ]
            )
            await message.reply_text(
                "Не удалось распознать данные задачи.\n\n"
                "Используйте формат по строкам:\n"
                "1 строка — название\n"
                "2 строка — описание\n"
                "3 строка — срок (завтра, сегодня или YYYY-MM-DD)\n\n"
                "Пример:\n"
                "Сделать математику\n"
                "Упражнение 2\n"
                "Завтра"
            )
            return

        try:
            task = await client.create_task_from_note(
                telegram_id=user.id,
                note_number=pending_note_number,
                title=parsed_task["title"],
                description=parsed_task.get("description"),
                due_date=parsed_task.get("due_date"),
            )

            context.user_data.pop("task_from_note_number", None)

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("📒 К заметкам", callback_data="back_to_notes")
                    ]
                ]
            )
            await message.reply_text(
                f"Задача #{task['user_task_number']} сохранена и привязана к заметке #{pending_note_number}.",
                reply_markup=keyboard,
            )
            return
        except Exception as e:
            await _safe_backend_error(message, e)
            return

    
    if parsed_task and not pending_note_number:
        await message.reply_text(
            "Сначала нужно создать заметку, а уже потом добавлять к ней задачу.\n\n"
            "Шаги:\n"
            "1. Отправьте обычный текст заметки\n"
            "2. Затем нажмите кнопку «Создать задачу»\n"
            "   или выполните команду /taskfromnote <номер заметки>\n"
            "3. После этого пришлите поля задачи"
        )
        return

    
    try:
        reply_to_id = (
            message.reply_to_message.message_id if message.reply_to_message else None
        )
        saved = await client.save_telegram_message(
            update_id=update.update_id,
            message_id=message.message_id,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
            chat_id=chat.id,
            chat_type=chat.type,
            text=message.text,
            reply_to_message_id=reply_to_id,
        )

        kind = saved.get("kind")
        if kind == "task_reminder_reply":
            title = saved.get("task_title") or "задача"
            num = saved.get("user_task_number")
            await message.reply_text(
                f"Записал ответ к задаче #{num}: «{title}»."
            )
            return
        if kind == "task_reminder_done":
            title = saved.get("task_title") or "задача"
            num = saved.get("user_task_number")
            await message.reply_text(
                f"Класс, отметил задачу #{num} «{title}» как выполненную. "
                f"Так держать — если что, напишу снова по другим делам."
            )
            return

        note_number = saved["user_note_number"]

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "Создать задачу",
                        callback_data=f"create_task:{note_number}",
                    ),
                    InlineKeyboardButton(
                        "Позже",
                        callback_data=f"later:{note_number}",
                    ),
                ]
            ]
        )

        await message.reply_text(
            "Заметка сохранена.\n\n"
            "Если это нужно выполнить, лучше оформить как задачу.",
            reply_markup=keyboard,
        )
    except Exception as e:
        await _safe_backend_error(message, e)

async def confirm_delete_note_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user

    if not query or not user:
        return

    await query.answer()

    try:
        note_number = int(query.data.split(":")[1])
    except (IndexError, ValueError):
        await query.edit_message_text("Ошибка номера заметки.")
        return

    try:
        await client.delete_note(
            telegram_id=user.id,
            note_number=note_number,
        )

        await query.edit_message_text(
            f"Заметка #{note_number} и все связанные задачи удалены.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("📒 К заметкам", callback_data="back_to_notes")]]
            ),
        )
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            await query.edit_message_text(
                "Заметка не найдена или уже была удалена.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("📒 К заметкам", callback_data="back_to_notes")]]
                ),
            )
            return
        await _safe_backend_error(query.message, e)
    except Exception as e:
        await query.edit_message_text(f"Ошибка: {e}")