import pytest

pytestmark = pytest.mark.asyncio


async def test_create_task(client, created_user, created_note):
    payload = {
        "title": "New task",
        "description": "Task description",
        "priority": "high",
        "status": "pending",
        "ai_generated": False,
        "user_id": created_user.id,
        "note_id": created_note.id
    }

    response = await client.post("/tasks", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["user_id"] == created_user.id
    assert data["note_id"] == created_note.id


async def test_create_task_missing_required_fields_returns_422(client, created_user):
    payload = {
        "description": "No title",
        "user_id": created_user.id
    }

    response = await client.post("/tasks", json=payload)
    assert response.status_code == 422


async def test_get_tasks_returns_list(client, created_task):
    response = await client.get("/tasks")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


async def test_get_task_by_id(client, created_task):
    response = await client.get(f"/tasks/{created_task.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_task.id
    assert data["title"] == created_task.title


async def test_get_task_nonexistent_returns_404(client):
    response = await client.get("/tasks/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


async def test_update_task(client, created_task):
    payload = {
        "title": "Updated task",
        "status": "done",
        "priority": "low"
    }

    response = await client.patch(f"/tasks/{created_task.id}", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated task"
    assert data["status"] == "done"
    assert data["priority"] == "low"


async def test_update_task_nonexistent_returns_404(client):
    payload = {"status": "done"}
    response = await client.patch("/tasks/999999", json=payload)

    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"


async def test_delete_task(client, created_user, created_note):
    payload = {
        "title": "Delete task",
        "description": "Delete me",
        "user_id": created_user.id,
        "note_id": created_note.id
    }
    create_response = await client.post("/tasks", json=payload)
    task_id = create_response.json()["id"]

    delete_response = await client.delete(f"/tasks/{task_id}")
    assert delete_response.status_code == 204

    get_response = await client.get(f"/tasks/{task_id}")
    assert get_response.status_code == 404


async def test_delete_task_nonexistent_returns_404(client):
    response = await client.delete("/tasks/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Task not found"