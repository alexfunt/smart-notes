"""Проверка Telegram WebApp initData (HMAC от bot_token).

Подробности: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl


class WebAppAuthError(ValueError):
    """Ошибка валидации initData."""


@dataclass(frozen=True)
class WebAppUser:
    id: int
    first_name: str | None
    last_name: str | None
    username: str | None
    language_code: str | None


@dataclass(frozen=True)
class WebAppAuth:
    user: WebAppUser
    auth_date: int


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()


def verify_init_data(
    init_data: str,
    bot_token: str,
    *,
    max_age_seconds: int = 86_400,
    now: int | None = None,
) -> WebAppAuth:
    """Проверяет подпись initData и возвращает пользователя.

    Поднимает WebAppAuthError при любой проблеме (нет hash, плохой hash, протухло, нет user).
    """
    if not init_data:
        raise WebAppAuthError("initData is empty")
    if not bot_token:
        raise WebAppAuthError("bot token is not configured")

    # Telegram отдаёт urlencoded строку; parse_qsl сохраняет порядок и декодирует значения.
    pairs = parse_qsl(init_data, keep_blank_values=True, strict_parsing=False)
    data = dict(pairs)

    received_hash = data.pop("hash", None)
    if not received_hash:
        raise WebAppAuthError("hash is missing in initData")

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    digest = hmac.new(
        _secret_key(bot_token), check_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(digest, received_hash):
        raise WebAppAuthError("initData hash mismatch")

    try:
        auth_date = int(data.get("auth_date", "0"))
    except ValueError as exc:
        raise WebAppAuthError("invalid auth_date") from exc

    current = now if now is not None else int(time.time())
    if auth_date <= 0 or current - auth_date > max_age_seconds:
        raise WebAppAuthError("initData is too old")

    user_raw = data.get("user")
    if not user_raw:
        raise WebAppAuthError("user payload is missing")

    try:
        user_obj = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise WebAppAuthError("user payload is not valid JSON") from exc

    if not isinstance(user_obj, dict) or "id" not in user_obj:
        raise WebAppAuthError("user.id is missing")

    return WebAppAuth(
        user=WebAppUser(
            id=int(user_obj["id"]),
            first_name=user_obj.get("first_name"),
            last_name=user_obj.get("last_name"),
            username=user_obj.get("username"),
            language_code=user_obj.get("language_code"),
        ),
        auth_date=auth_date,
    )
