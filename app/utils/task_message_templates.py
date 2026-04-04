"""Тексты напоминаний по задачам — из app/messages/task_reminders.yaml (случайный выбор)."""

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


def _pick(category: str, title: str) -> str:
    items = _data().get(category) or []
    if not items:
        raise ValueError(f"Missing or empty list in task_reminders.yaml: {category}")
    template = random.choice(items)
    return template.replace("{title}", title)


def random_reminder_text(title: str) -> str:
    return _pick("reminders", title).strip()


def random_overdue_text(title: str) -> str:
    return _pick("overdue", title).strip()
