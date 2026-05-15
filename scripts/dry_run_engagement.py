#!/usr/bin/env python3
"""
Прогон оценки вовлечённости без Telegram: те же формулы, что при реплае на напоминание.

Запуск из корня репозитория:
  PYTHONPATH=. python scripts/dry_run_engagement.py "пока в работе"
  PYTHONPATH=. python scripts/dry_run_engagement.py --due 2026-04-01 --prev 0.5 "сделал шаги 1–2, жду ответа от Ивана"
  echo "норм" | PYTHONPATH=. python scripts/dry_run_engagement.py --json

Переменные из .env (OPENAI_API_KEY, LLM_CHAT_BASE_URL, OPENAI_MODEL) влияют на шаг llm_score.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_ROOT / ".env")


def _parse_due(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    if "T" in raw:
        d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    dd = date.fromisoformat(raw)
    return datetime(dd.year, dd.month, dd.day, tzinfo=timezone.utc)


def _parse_now(raw: str | None) -> datetime:
    if not raw:
        return datetime.now(timezone.utc)
    d = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def main() -> None:
    p = argparse.ArgumentParser(description="Dry-run reminder engagement scoring")
    p.add_argument(
        "text",
        nargs="?",
        default=None,
        help="Текст ответа пользователя (если нет — читается из stdin)",
    )
    p.add_argument(
        "--due",
        metavar="DATE",
        help="Срок задачи: YYYY-MM-DD или ISO datetime",
    )
    p.add_argument(
        "--now",
        metavar="ISO",
        help="«Сейчас» для расчёта просрочки (по умолчанию UTC now)",
    )
    p.add_argument(
        "--prev",
        type=float,
        metavar="SCORE",
        help="Текущий engagement_score задачи (0..1) — показать смешивание с историей",
    )
    p.add_argument(
        "--json",
        action="store_true",
        help="Одна строка JSON (удобно копить в файл для датасета)",
    )
    args = p.parse_args()

    text = args.text
    if text is None:
        text = sys.stdin.read()
    text = text.strip()
    if not text:
        p.error("пустой текст ответа")

    # Импорт после load_dotenv, чтобы подтянулись ключи API
    from app.core.config import settings
    from app.services.task_engagement import (
        blend_engagement_with_history,
        engagement_to_priority,
        reminder_engagement_breakdown,
    )

    due = _parse_due(args.due)
    now = _parse_now(args.now)

    async def _run():
        return await reminder_engagement_breakdown(text, due, now)

    b = asyncio.run(_run())

    extra: dict = {
        "reply_preview": text[:500],
        "due_iso": due.isoformat() if due else None,
        "now_iso": now.isoformat(),
        "llm_configured": bool(settings.OPENAI_API_KEY),
        "llm_base_url": settings.LLM_CHAT_BASE_URL,
        "llm_model": settings.OPENAI_MODEL,
    }
    if args.prev is not None:
        prev = max(0.0, min(1.0, args.prev))
        blended = blend_engagement_with_history(prev, b.new_reply_score)
        extra["previous_engagement_score"] = prev
        extra["blended_engagement_score"] = blended
        extra["blended_priority"] = engagement_to_priority(blended)

    if args.json:
        out = {**b.as_json_dict(), **extra}
        print(json.dumps(out, ensure_ascii=False))
        return

    print("--- Разбор new_reply_score (один ответ, как в score_reminder_reply) ---")
    print(f"  heuristic_reply_quality: {b.heuristic_reply_quality:.4f}")
    print(f"  due_urgency:             {b.due_urgency:.4f}")
    print(f"  base_before_llm:         {b.base_before_llm:.4f}")
    if b.llm_score is None:
        print("  llm_score:               (нет — нет ключа API или ошибка запроса)")
    else:
        print(f"  llm_score:               {b.llm_score:.4f}")
    print(f"  new_reply_score:         {b.new_reply_score:.4f}")
    print(f"  priority:                {b.priority}")
    print(f"  offer_ai_hint:           {b.offer_ai_hint}")
    if args.prev is not None:
        print("--- После смешивания с историей задачи (0.48·prev + 0.52·new) ---")
        print(f"  blended_engagement_score: {extra['blended_engagement_score']:.4f}")
        print(f"  blended_priority:         {extra['blended_priority']}")


if __name__ == "__main__":
    main()
