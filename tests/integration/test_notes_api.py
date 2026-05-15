import pytest

pytestmark = pytest.mark.asyncio


async def test_create_note(client, created_user):
    payload = {
        "title": "My note",
        "content": "Some content",
        "source": "web",
        "note_type": "plain",
        "status": "active",
        "metadata_json": {"topic": "study"},
        "user_id": created_user.id
    }

    response = await client.post("/notes", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == payload["title"]
    assert data["content"] == payload["content"]
    assert data["user_id"] == created_user.id
    assert "id" in data
    assert "user_note_number" in data


async def test_create_note_missing_required_fields_returns_422(client, created_user):
    payload = {
        "content": "Missing title",
        "user_id": created_user.id
    }

    response = await client.post("/notes", json=payload)
    assert response.status_code == 422


async def test_get_notes_returns_list(client, created_note):
    response = await client.get("/notes")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


async def test_get_note_by_id(client, created_note):
    response = await client.get(f"/notes/{created_note.id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == created_note.id
    assert data["title"] == created_note.title


async def test_get_note_by_nonexistent_id_returns_404(client):
    response = await client.get("/notes/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Note not found"


async def test_update_note(client, created_note):
    payload = {
        "title": "Updated title",
        "content": "Updated content"
    }

    response = await client.patch(f"/notes/{created_note.id}", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Updated title"
    assert data["content"] == "Updated content"


async def test_update_note_nonexistent_returns_404(client):
    payload = {"title": "No note"}
    response = await client.patch("/notes/999999", json=payload)

    assert response.status_code == 404
    assert response.json()["detail"] == "Note not found"


async def test_delete_note(client, created_user):
    create_payload = {
        "title": "To delete",
        "content": "Delete me",
        "user_id": created_user.id
    }
    create_response = await client.post("/notes", json=create_payload)
    note_id = create_response.json()["id"]

    delete_response = await client.delete(f"/notes/{note_id}")
    assert delete_response.status_code == 204

    get_response = await client.get(f"/notes/{note_id}")
    assert get_response.status_code == 404


async def test_delete_note_nonexistent_returns_404(client):
    response = await client.delete("/notes/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Note not found"