from datetime import datetime, timedelta
from urllib.parse import urlencode, urlparse

from telegram import InlineKeyboardButton, WebAppInfo

from app.core.config import settings


def build_web_app_url(telegram_id: int | None = None) -> str:
    """Полный URL фронта; при наличии telegram_id добавляет ?tg_id=… как fallback.

    Гарантирует наличие пути перед query — некоторые клиенты Telegram отказываются
    открывать URL вида http://host?x=y (без слэша после порта/хоста).
    """
    raw = (settings.WEB_APP_URL or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    path = parsed.path or "/"
    base = f"{parsed.scheme}://{parsed.netloc}{path}"
    query = parsed.query
    if telegram_id is not None:
        extra = urlencode({"tg_id": telegram_id})
        query = f"{query}&{extra}" if query else extra
    return f"{base}?{query}" if query else base


def open_app_button(telegram_id: int | None = None, label: str = "🌐 Открыть приложение") -> InlineKeyboardButton | None:
    """Кнопка открытия веб-версии.

    https → нативная WebApp-кнопка (initData на фронте).
    http (например, localhost) → callback-кнопка: по тапу бот пришлёт ссылку текстом
        (Telegram не разрешает http в url-кнопках, но в тексте автоматически линкует).
    Пусто → None.
    """
    url = build_web_app_url(telegram_id)
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme == "https":
        return InlineKeyboardButton(label, web_app=WebAppInfo(url=build_web_app_url(None)))
    return InlineKeyboardButton(label, callback_data="open_app")




def label_for_button(text: str | None, max_len: int = 44) -> str:
    """Короткая подпись для InlineKeyboard (без номеров — только смысл)."""
    t = (text or "").strip().replace("\n", " ")
    if not t:
        return "…"
    if len(t) <= max_len:
        return t
    return t[: max_len - 1].rstrip() + "…"


def note_button_caption(note: dict, max_len: int = 44) -> str:
    t = (note.get("title") or "").strip()
    if not t:
        t = (note.get("content") or "").strip().replace("\n", " ")
    return label_for_button(t, max_len)


def parse_human_date(text: str | None) -> str | None:
    if not text:
        return None

    text = text.strip().lower()
    today = datetime.now()

    if text in {"сегодня", "today"}:
        return today.strftime("%Y-%m-%d")

    if text in {"завтра", "tomorrow"}:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    return text


def parse_task_template(text: str) -> dict | None:
    """
    Формат:
    1 строка — название
    2 строка — описание
    3 строка — срок (опционально: «завтра», YYYY-MM-DD, …)

    Приоритет не вводится: выставляется автоматически (medium), дальше — по ответам на напоминания.
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    if len(lines) < 2:
        return None

    title = lines[0]
    description = lines[1] if len(lines) >= 2 else None
    due_date_raw = lines[2] if len(lines) >= 3 else None

    return {
        "title": title,
        "description": description,
        "due_date": parse_human_date(due_date_raw) if due_date_raw else None,
        "priority": "medium",
    }