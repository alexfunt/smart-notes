import pytest

pytestmark = pytest.mark.asyncio


async def test_get_user_notes_by_telegram_id(client, created_user, created_note):
    response = await client.get(f"/telegram/users/{created_user.telegram_id}/notes")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert any(note["id"] == created_note.id for note in data)


async def test_get_user_notes_for_unknown_telegram_user_returns_empty_list(client):
    response = await client.get("/telegram/users/999999999/notes")

    assert response.status_code == 200
    assert response.json() == []


async def test_get_user_note_details(client, created_user, created_note):
    response = await client.get(
        f"/telegram/users/{created_user.telegram_id}/notes/{created_note.user_note_number}"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_note.id
    assert data["user_note_number"] == created_note.user_note_number
    assert "tasks" in data
    assert isinstance(data["tasks"], list)


async def test_get_user_note_details_with_focus_note(client, created_user, created_note):
    response = await client.get(
        f"/telegram/users/{created_user.telegram_id}/notes/{created_note.user_note_number}?focus=note"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_note.id


async def test_get_user_note_details_with_focus_task(client, created_user, created_note):
    response = await client.get(
        f"/telegram/users/{created_user.telegram_id}/notes/{created_note.user_note_number}?focus=task"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_note.id


async def test_get_user_note_details_with_invalid_focus_returns_400(client, created_user, created_note):
    response = await client.get(
        f"/telegram/users/{created_user.telegram_id}/notes/{created_note.user_note_number}?focus=wrong"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "focus must be 'note' or 'task'"


async def test_get_user_note_details_nonexistent_returns_404(client, created_user):
    response = await client.get(
        f"/telegram/users/{created_user.telegram_id}/notes/999999"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Note not found"


async def test_create_task_from_note(client, created_user, created_note):
    payload = {
        "title": "Telegram task",
        "description": "Created from telegram API",
        "due_date": "2026-04-20"
    }

    response = await client.post(
        f"/telegram/users/{created_user.telegram_id}/notes/{created_note.user_note_number}/tasks",
        json=payload
    )

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Telegram task"
    assert data["status"] == "pending"
    assert data["note_id"] == created_note.id


async def test_create_task_from_note_without_title_returns_400(client, created_user, created_note):
    payload = {"description": "No title"}

    response = await client.post(
        f"/telegram/users/{created_user.telegram_id}/notes/{created_note.user_note_number}/tasks",
        json=payload
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "title is required"


async def test_create_task_from_note_nonexistent_note_returns_404(client, created_user):
    payload = {"title": "Task for missing note"}

    response = await client.post(
        f"/telegram/users/{created_user.telegram_id}/notes/999999/tasks",
        json=payload
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Note not found"


async def test_toggle_task_status(client, created_user, created_task):
    response = await client.patch(
        f"/telegram/users/{created_user.telegram_id}/tasks/{created_task.id}/toggle"
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_task.id
    assert data["status"] in ("pending", "done")


async def test_toggle_task_status_nonexistent_returns_404(client, created_user):
    response = await client.patch(
        f"/telegram/users/{created_user.telegram_id}/tasks/999999/toggle"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


async def test_delete_user_task(client, created_user, created_task):
    response = await client.delete(
        f"/telegram/users/{created_user.telegram_id}/tasks/{created_task.id}"
    )
    assert response.status_code == 204

    get_response = await client.get(f"/tasks/{created_task.id}")
    assert get_response.status_code == 404


async def test_update_user_note(client, created_user, created_note):
    payload = {"content": "Updated from telegram"}

    response = await client.patch(
        f"/telegram/users/{created_user.telegram_id}/notes/{created_note.user_note_number}",
        json=payload
    )

    assert response.status_code == 200
    data = response.json()
    assert data["content"] == "Updated from telegram"
    assert data["title"] == "Updated from telegram"


async def test_update_user_note_without_content_returns_400(client, created_user, created_note):
    response = await client.patch(
        f"/telegram/users/{created_user.telegram_id}/notes/{created_note.user_note_number}",
        json={}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "content is required"


async def test_delete_user_note(client, created_user, created_note):
    response = await client.delete(
        f"/telegram/users/{created_user.telegram_id}/notes/{created_note.user_note_number}"
    )
    assert response.status_code == 204

    get_response = await client.get(f"/notes/{created_note.id}")
    assert get_response.status_code == 404


async def test_delete_user_note_nonexistent_returns_404(client, created_user):
    response = await client.delete(
        f"/telegram/users/{created_user.telegram_id}/notes/999999"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Note not found"


async def test_webhook_without_message_is_ignored(client):
    payload = {
        "update_id": 1001,
        "message": None
    }

    response = await client.post("/telegram/webhook", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert response.json()["reason"] == "no_message"


async def test_webhook_without_text_is_ignored(client):
    payload = {
        "update_id": 1002,
        "message": {
            "message_id": 1,
            "from_user": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "Test",
                "username": "tester"
            },
            "chat": {
                "id": 123456789,
                "type": "private"
            }
        }
    }

    response = await client.post("/telegram/webhook", json=payload)

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert response.json()["reason"] == "no_text"


async def test_webhook_creates_note_from_text_message(client):
    payload = {
        "update_id": 1003,
        "message": {
            "message_id": 2,
            "from_user": {
                "id": 777000111,
                "is_bot": False,
                "first_name": "Alice",
                "last_name": "Smith",
                "username": "alice_s"
            },
            "chat": {
                "id": 777000111,
                "type": "private"
            },
            "text": "My note from telegram"
        }
    }

    response = await client.post("/telegram/webhook", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["message"] == "Telegram message saved as note"
    assert "note_id" in data
    assert "user_note_number" in data