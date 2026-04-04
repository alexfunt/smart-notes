"""
Оценка вовлечённости по ответу на напоминание + срочность по сроку.

Обучаемый QRNN здесь не используется: нужны размеченные данные и отдельный ML-пайплайн.
Вместо этого — эвристики и (опционально) LLM по OpenAI-совместимому API (OpenAI, DeepSeek и т.д.).
Поле engagement_score (0..1) и производный строковый priority — основа для будущих
AI-подсказок (см. settings.AI_HINT_MIN_ENGAGEMENT_SCORE).
Интервал напоминаний масштабируется: выше вовлечённость — чаще, ниже — реже (reminder_delta_for_engagement).
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_VAGUE = (
    "пока в работе",
    "пока работаю",
    "еще не",
    "ещё не",
    "не сделал",
    "не сделала",
    "потом",
    "скоро",
    "не успел",
    "не успела",
    "забыл",
    "забыла",
    "отложил",
    "позже",
    "ничего",
    "пока нет",
    "в процессе",
    "делаю",
    "так себе",
    "норм",
)

_SUBSTANTIVE = (
    "потому что",
    "план",
    "шаг",
    "сегодня сделаю",
    "завтра сделаю",
    "закончил",
    "разобрался",
    "проблема",
    "вопрос",
    "нужно",
    "жду ответ",
    "блокер",
    "риск",
)


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def heuristic_reply_quality(text: str) -> float:
    t = text.strip().lower().replace("ё", "е")
    t = re.sub(r"\s+", " ", t)
    if not t:
        return 0.22
    score = 0.52
    n = len(t)
    if n < 12:
        score -= 0.28
    elif n < 35:
        score -= 0.12
    elif n > 120:
        score += 0.18
    elif n > 60:
        score += 0.1
    for v in _VAGUE:
        if v in t:
            score -= 0.11
    for s in _SUBSTANTIVE:
        if s in t:
            score += 0.07
    return _clamp(score)


def due_date_urgency(due: datetime | None, now: datetime) -> float:
    if not due:
        return 0.42
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    d_d = due.astimezone(timezone.utc).date()
    n_d = now.astimezone(timezone.utc).date()
    if n_d > d_d:
        return 1.0
    delta = (d_d - n_d).days
    if delta == 0:
        return 0.82
    if delta <= 2:
        return 0.68
    if delta <= 7:
        return 0.52
    return 0.38


def combine_reply_and_due(reply_quality: float, urgency: float) -> float:
    return _clamp(0.55 * reply_quality + 0.45 * urgency)


def blend_engagement_with_history(
    previous_task_engagement: float, new_reply_score: float
) -> float:
    """Как в TaskRepository.apply_engagement_after_reminder_reply."""
    return max(
        0.0,
        min(1.0, 0.48 * previous_task_engagement + 0.52 * new_reply_score),
    )


def reminder_delta_for_engagement(
    engagement_score: float, base: timedelta | None = None
) -> timedelta:
    """
    Пауза до следующего напоминания относительно базового интервала.

    engagement → 1: множитель MIN (напоминать чаще).
    engagement → 0: множитель MAX (реже, без отключения).
    """
    if base is None:
        base = settings.task_reminder_delta()
    e = _clamp(float(engagement_score))
    hi = settings.TASK_REMINDER_ENGAGEMENT_MIN_GAP_MULTIPLIER
    lo = settings.TASK_REMINDER_ENGAGEMENT_MAX_GAP_MULTIPLIER
    if lo < hi:
        lo, hi = hi, lo
    mult = hi + (lo - hi) * (1.0 - e)
    minutes = (base.total_seconds() / 60.0) * mult
    floor_m = max(1, int(settings.REMINDER_MIN_SPACING_MINUTES))
    minutes = max(float(floor_m), minutes)
    return timedelta(minutes=minutes)


def _due_date_label(due_date: datetime | None) -> str | None:
    if not due_date:
        return None
    dd = due_date
    if dd.tzinfo is None:
        dd = dd.replace(tzinfo=timezone.utc)
    return dd.astimezone(timezone.utc).date().isoformat()


@dataclass(frozen=True)
class ReminderEngagementBreakdown:
    """Пошаговый разбор score для отладки и сбора датасета."""

    heuristic_reply_quality: float
    due_urgency: float
    base_before_llm: float
    llm_score: float | None
    new_reply_score: float
    priority: str
    offer_ai_hint: bool

    def as_json_dict(self) -> dict:
        return asdict(self)


async def reminder_engagement_breakdown(
    reply_text: str, due_date: datetime | None, now: datetime
) -> ReminderEngagementBreakdown:
    hq = heuristic_reply_quality(reply_text)
    urg = due_date_urgency(due_date, now)
    base = combine_reply_and_due(hq, urg)
    due_label = _due_date_label(due_date)
    llm = await llm_refine_score(reply_text, due_label)
    if llm is not None:
        new = _clamp(0.42 * base + 0.58 * llm)
    else:
        new = base
    return ReminderEngagementBreakdown(
        heuristic_reply_quality=hq,
        due_urgency=urg,
        base_before_llm=base,
        llm_score=llm,
        new_reply_score=new,
        priority=engagement_to_priority(new),
        offer_ai_hint=should_offer_ai_hint(new),
    )


async def llm_refine_score(reply_text: str, due_label: str | None) -> float | None:
    if not settings.OPENAI_API_KEY:
        return None
    url = f"{settings.LLM_CHAT_BASE_URL.rstrip('/')}/chat/completions"
    body = {
        "model": settings.OPENAI_MODEL,
        "temperature": 0.15,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "Оцени вовлечённость пользователя в ответе на напоминание о задаче. "
                    'Верни строго JSON: {"score": число от 0 до 1}. '
                    "Короткие отписки вроде «пока в работе», «ещё нет» — низкий score. "
                    "Развёрнутый отчёт, план, конкретика — высокий."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Срок (дата, если известна): {due_label or 'не указан'}\n\nОтвет:\n"
                    f"{reply_text[:3500]}"
                ),
            },
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            r = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=body,
            )
            try:
                r.raise_for_status()
            except httpx.HTTPStatusError as e:
                snippet = (e.response.text or "")[:800]
                logger.warning(
                    "LLM engagement score HTTP %s: %s",
                    e.response.status_code,
                    snippet or str(e),
                )
                return None
            data = r.json()
            raw = data["choices"][0]["message"]["content"]
            obj = json.loads(raw)
            return _clamp(float(obj["score"]))
    except Exception as e:
        logger.warning("LLM engagement score failed: %s", e)
        return None


async def score_reminder_reply(
    reply_text: str, due_date: datetime | None, now: datetime
) -> float:
    b = await reminder_engagement_breakdown(reply_text, due_date, now)
    return b.new_reply_score


def engagement_to_priority(score: float) -> str:
    if score < 0.38:
        return "low"
    if score < 0.65:
        return "medium"
    return "high"


def should_offer_ai_hint(engagement_score: float) -> bool:
    return engagement_score >= settings.AI_HINT_MIN_ENGAGEMENT_SCORE
