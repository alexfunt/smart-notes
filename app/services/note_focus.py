"""
Вес «темы» (заметки) по фактическому вниманию пользователя — без LLM.

Заметка = корзина темы; focus_score растёт от открытий и действий.
Итоговый порядок в /notes считается в NoteRepository.get_all_by_user_id:
ещё и средняя вовлечённость по задачам, число задач и выполненных.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

# Множитель за каждый полный день без взаимодействия с темой (затухание шума).
_FOCUS_DECAY_PER_DAY = 0.92


class FocusEvent(str, Enum):
    NOTE_OPEN = "note_open"
    TASK_OPEN = "task_open"
    TASK_DONE = "task_done"
    REMINDER_REPLY = "reminder_reply"
    NEW_NOTE = "new_note"
    TASK_CREATED = "task_created"


_INCREMENTS: dict[FocusEvent, float] = {
    FocusEvent.NOTE_OPEN: 0.08,
    FocusEvent.TASK_OPEN: 0.05,
    FocusEvent.TASK_DONE: 0.12,
    FocusEvent.REMINDER_REPLY: 0.06,
    FocusEvent.NEW_NOTE: 0.04,
    FocusEvent.TASK_CREATED: 0.05,
}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def decay_focus(score: float, last_focus_at: datetime | None, now: datetime) -> float:
    if last_focus_at is None:
        return score
    if last_focus_at.tzinfo is None:
        last_focus_at = last_focus_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    days = max(0.0, (now - last_focus_at).total_seconds() / 86400.0)
    factor = _FOCUS_DECAY_PER_DAY ** min(days, 90.0)
    return _clamp(score * factor)


def apply_focus_delta(
    score: float,
    last_focus_at: datetime | None,
    now: datetime,
    event: FocusEvent,
) -> tuple[float, datetime]:
    decayed = decay_focus(score, last_focus_at, now)
    inc = _INCREMENTS[event]
    return _clamp(decayed + inc), now
