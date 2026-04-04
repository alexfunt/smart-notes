from datetime import datetime, timedelta


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