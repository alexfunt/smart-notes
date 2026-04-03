import httpx

from app.core.config import settings


class BackendClient:
    def __init__(self):
        self.base_url = settings.BACKEND_API_URL.rstrip("/")

    async def auth_telegram_user(
        self,
        telegram_id: int,
        username: str | None,
        full_name: str | None,
    ) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/auth/telegram",
                json={
                    "telegram_id": telegram_id,
                    "username": username,
                    "full_name": full_name,
                },
            )
            response.raise_for_status()
            return response.json()

    async def save_telegram_message(
        self,
        update_id: int,
        message_id: int,
        user_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        chat_id: int,
        chat_type: str,
        text: str,
    ) -> dict:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.base_url}/telegram/webhook",
                json={
                    "update_id": update_id,
                    "message": {
                        "message_id": message_id,
                        "from_user": {
                            "id": user_id,
                            "is_bot": False,
                            "first_name": first_name,
                            "last_name": last_name,
                            "username": username,
                        },
                        "chat": {
                            "id": chat_id,
                            "type": chat_type,
                        },
                        "text": text,
                    },
                },
            )
            response.raise_for_status()
            return response.json()

    async def get_user_notes(self, telegram_id: int) -> list[dict]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{self.base_url}/telegram/users/{telegram_id}/notes"
            )
            response.raise_for_status()
            return response.json()

    async def get_user_note_details(self, telegram_id: int, note_number: int) -> dict:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(
                f"{self.base_url}/telegram/users/{telegram_id}/notes/{note_number}"
            )
            response.raise_for_status()
            return response.json()

    async def create_task_from_note(
        self,
        telegram_id: int,
        note_number: int,
        title: str,
        description: str | None,
        due_date: str | None,
        priority: str,
    ) -> dict:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.base_url}/telegram/users/{telegram_id}/notes/{note_number}/tasks",
                json={
                    "title": title,
                    "description": description,
                    "due_date": due_date,
                    "priority": priority,
                },
            )
            response.raise_for_status()
            return response.json()

    async def update_user_note(self, telegram_id: int, note_number: int, content: str) -> dict:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.patch(
                f"{self.base_url}/telegram/users/{telegram_id}/notes/{note_number}",
                json={"content": content},
            )
            response.raise_for_status()
            return response.json()

    async def delete_note(self, telegram_id: int, note_number: int) -> None:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.delete(
                f"{self.base_url}/telegram/users/{telegram_id}/notes/{note_number}"
            )
            response.raise_for_status()

    async def get_tasks(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.get(f"{self.base_url}/tasks")
            response.raise_for_status()
            return response.json()

    async def toggle_task(self, telegram_id: int, task_id: int) -> dict:
        async with httpx.AsyncClient(timeout=20.0) as client:
            url = f"{self.base_url}/telegram/users/{telegram_id}/tasks/{task_id}/toggle"
            print("TOGGLE URL:", url)
            response = await client.patch(url)
            print("TOGGLE STATUS:", response.status_code)
            print("TOGGLE BODY:", response.text)
            response.raise_for_status()
            return response.json()