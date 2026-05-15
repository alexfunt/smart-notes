import random
import uuid
from locust import HttpUser, task, between


class TelegramFlowUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        self.user = None
        self.note_id = None
        self.note_number = None
        self.task_id = None

        tg_id = random.randint(200_000_000, 999_999_999)

        auth_payload = {
            "telegram_id": tg_id,
            "username": f"tg_{uuid.uuid4().hex[:8]}",
            "full_name": "Telegram Load User"
        }

        auth_response = self.client.post(
            "/auth/telegram",
            json=auth_payload,
            name="POST /auth/telegram"
        )

        if auth_response.status_code == 200:
            self.user = auth_response.json()

            note_payload = {
                "title": f"Telegram seed {uuid.uuid4().hex[:6]}",
                "content": "Seed note for telegram load flow",
                "source": "telegram",
                "note_type": "plain",
                "status": "active",
                "metadata_json": {"seed": "telegram"},
                "user_id": self.user["id"]
            }

            note_response = self.client.post(
                "/notes",
                json=note_payload,
                name="POST /notes [telegram setup]"
            )

            if note_response.status_code == 201:
                note_data = note_response.json()
                self.note_id = note_data["id"]
                self.note_number = note_data["user_note_number"]

    @task(3)
    def get_user_notes(self):
        if not self.user:
            return

        self.client.get(
            f"/telegram/users/{self.user['telegram_id']}/notes",
            name="GET /telegram/users/{telegram_id}/notes"
        )

    @task(2)
    def get_user_note_details(self):
        if not self.user or not self.note_number:
            return

        self.client.get(
            f"/telegram/users/{self.user['telegram_id']}/notes/{self.note_number}",
            name="GET /telegram/users/{telegram_id}/notes/{note_number}"
        )

    @task(1)
    def get_user_note_details_focus_note(self):
        if not self.user or not self.note_number:
            return

        self.client.get(
            f"/telegram/users/{self.user['telegram_id']}/notes/{self.note_number}?focus=note",
            name="GET /telegram/users/{telegram_id}/notes/{note_number}?focus=note"
        )

    @task(1)
    def get_user_note_details_focus_task(self):
        if not self.user or not self.note_number:
            return

        self.client.get(
            f"/telegram/users/{self.user['telegram_id']}/notes/{self.note_number}?focus=task",
            name="GET /telegram/users/{telegram_id}/notes/{note_number}?focus=task"
        )

    @task(2)
    def create_task_from_note(self):
        if not self.user or not self.note_number:
            return

        payload = {
            "title": f"TG task {uuid.uuid4().hex[:6]}",
            "description": "Created from telegram flow",
            "due_date": "2026-12-31"
        }

        response = self.client.post(
            f"/telegram/users/{self.user['telegram_id']}/notes/{self.note_number}/tasks",
            json=payload,
            name="POST /telegram/users/{telegram_id}/notes/{note_number}/tasks"
        )

        if response.status_code == 200:
            self.task_id = response.json()["id"]

    @task(1)
    def toggle_task(self):
        if not self.user or not self.task_id:
            return

        self.client.patch(
            f"/telegram/users/{self.user['telegram_id']}/tasks/{self.task_id}/toggle",
            name="PATCH /telegram/users/{telegram_id}/tasks/{task_id}/toggle"
        )

    @task(1)
    def delete_user_task(self):
        if not self.user or not self.task_id:
            return

        response = self.client.delete(
            f"/telegram/users/{self.user['telegram_id']}/tasks/{self.task_id}",
            name="DELETE /telegram/users/{telegram_id}/tasks/{task_id}"
        )

        if response.status_code == 204:
            self.task_id = None