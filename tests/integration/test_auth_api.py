import pytest

pytestmark = pytest.mark.asyncio


async def test_auth_telegram_creates_or_returns_user(client):
    payload = {
        "telegram_id": 999001,
        "username": "tg_user",
        "full_name": "Telegram User"
    }

    response = await client.post("/auth/telegram", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert data["telegram_id"] == payload["telegram_id"]
    assert data["username"] == payload["username"]
    assert data["full_name"] == payload["full_name"]
    assert "id" in data


async def test_auth_telegram_without_required_telegram_id_returns_422(client):
    payload = {
        "username": "broken_user",
        "full_name": "Broken User"
    }

    response = await client.post("/auth/telegram", json=payload)
    assert response.status_code == 422


async def test_auth_telegram_is_idempotent_for_same_user(client):
    payload = {
        "telegram_id": 555777,
        "username": "same_user",
        "full_name": "Same User"
    }

    r1 = await client.post("/auth/telegram", json=payload)
    r2 = await client.post("/auth/telegram", json=payload)

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["telegram_id"] == r2.json()["telegram_id"]