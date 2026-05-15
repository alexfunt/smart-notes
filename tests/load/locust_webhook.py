import random
import uuid
from locust import HttpUser, task, between


class TelegramWebhookUser(HttpUser):
    wait_time = between(1, 2)

    @task(3)
    def webhook_text_message(self):
        tg_id = random.randint(300_000_000, 999_999_999)
        msg_id = random.randint(1, 1_000_000)
        upd_id = random.randint(1, 10_000_000)

        payload = {
            "update_id": upd_id,
            "message": {
                "message_id": msg_id,
                "from_user": {
                    "id": tg_id,
                    "is_bot": False,
                    "first_name": "Load",
                    "last_name": "User",
                    "username": f"webhook_{uuid.uuid4().hex[:6]}"
                },
                "chat": {
                    "id": tg_id,
                    "type": "private"
                },
                "text": f"Webhook message {uuid.uuid4().hex[:8]}"
            }
        }

        self.client.post(
            "/telegram/webhook",
            json=payload,
            name="POST /telegram/webhook [text]"
        )

    @task(1)
    def webhook_without_text(self):
        tg_id = random.randint(300_000_000, 999_999_999)
        msg_id = random.randint(1, 1_000_000)
        upd_id = random.randint(1, 10_000_000)

        payload = {
            "update_id": upd_id,
            "message": {
                "message_id": msg_id,
                "from_user": {
                    "id": tg_id,
                    "is_bot": False,
                    "first_name": "Load",
                    "username": f"empty_{uuid.uuid4().hex[:6]}"
                },
                "chat": {
                    "id": tg_id,
                    "type": "private"
                }
            }
        }

        self.client.post(
            "/telegram/webhook",
            json=payload,
            name="POST /telegram/webhook [no_text]"
        )

    @task(1)
    def webhook_without_message(self):
        payload = {
            "update_id": random.randint(1, 10_000_000),
            "message": None
        }

        self.client.post(
            "/telegram/webhook",
            json=payload,
            name="POST /telegram/webhook [no_message]"
        )