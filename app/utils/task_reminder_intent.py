import re

# Сначала отсекаем явный отказ / «ещё нет»
_NEGATIVE_PHRASES = (
    "ещё нет",
    "еще нет",
    "пока нет",
    "не готов",
    "не готова",
    "не готовы",
    "не готово",
    "не выполнил",
    "не выполнила",
    "не сделал",
    "не сделала",
    "не успел",
    "не успела",
    "в процессе",
    "позже сделаю",
    "завтра сделаю",
    "не сегодня",
)

_POSITIVE_MARKERS = (
    "выполнил",
    "выполнила",
    "выполнили",
    "выполнено",
    "готово",
    "готов",
    "готова",
    "готовы",
    "сделал",
    "сделала",
    "сделали",
    "сделано",
    "закончил",
    "закончила",
    "завершил",
    "завершила",
    "завершено",
    "справился",
    "справилась",
    "сделано",
)

_SHORT_ACK = frozenset(
    {
        "да",
        "yes",
        "y",
        "ok",
        "ок",
        "угу",
        "ага",
        "+",
        "окей",
        "okay",
    }
)


def is_task_done_acknowledgment(raw: str) -> bool:
    """Реплай на напоминание трактуем как «задача выполнена», а не как текст к описанию."""
    t = raw.strip().lower().replace("ё", "е")
    t = re.sub(r"[^\w\s\-+]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    if not t:
        return False
    for neg in _NEGATIVE_PHRASES:
        if neg in t:
            return False
    if t in _SHORT_ACK:
        return True
    for pos in _POSITIVE_MARKERS:
        if pos in t:
            return True
    return False
