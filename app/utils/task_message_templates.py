"""Тексты напоминаний — app/messages/task_reminders.yaml (случайный выбор)."""

from __future__ import annotations

import random
from functools import lru_cache
from pathlib import Path

import yaml

_YAML_PATH = Path(__file__).resolve().parent.parent / "messages" / "task_reminders.yaml"


@lru_cache(maxsize=1)
def _data() -> dict:
    with _YAML_PATH.open(encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    if not isinstance(loaded, dict):
        raise ValueError("task_reminders.yaml must be a mapping")
    return loaded


def _note_label(note_title: str | None) -> str:
    t = (note_title or "").strip()
    return t if t else "твоя заметка"


def _pick(category: str, task_title: str, note_title: str | None) -> str:
    items = _data().get(category) or []
    if not items:
        raise ValueError(f"Missing or empty list in task_reminders.yaml: {category}")
    template = random.choice(items)
    nt = _note_label(note_title)
    return template.replace("{title}", task_title).replace("{note_title}", nt)


def random_reminder_text(task_title: str, note_title: str | None = None) -> str:
    return _pick("reminders", task_title, note_title).strip()


def random_overdue_text(task_title: str, note_title: str | None = None) -> str:
    return _pick("overdue", task_title, note_title).strip()
