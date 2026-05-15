from datetime import datetime, timezone
import pytest

from app.services.telegram_service import TelegramService, _parse_due_date_text


class FakeUser:
    def __init__(self, id, telegram_id, username=None, full_name=None):
        self.id = id
        self.telegram_id = telegram_id
        self.username = username
        self.full_name = full_name


class FakeNote:
    def __init__(self, id, user_id, user_note_number, title, content, note_id=None):
        self.id = id
        self.user_id = user_id
        self.user_note_number = user_note_number
        self.title = title
        self.content = content
        self.note_id = note_id


class FakeTask:
    def __init__(self, id, user_id, title, status="pending", note_id=None, user_task_number=1):
        self.id = id
        self.user_id = user_id
        self.title = title
        self.status = status
        self.note_id = note_id
        self.user_task_number = user_task_number


class FakeUserRepo:
    def __init__(self):
        self.users = {}
        self.next_id = 1

    async def get_by_telegram_id(self, telegram_id):
        return self.users.get(telegram_id)

    async def create(self, user_create):
        user = FakeUser(
            id=self.next_id,
            telegram_id=user_create.telegram_id,
            username=user_create.username,
            full_name=user_create.full_name,
        )
        self.users[user.telegram_id] = user
        self.next_id += 1
        return user


class FakeNoteRepo:
    def __init__(self):
        self.notes = {}
        self.next_id = 1

    async def create(self, note_create):
        note = FakeNote(
            id=self.next_id,
            user_id=note_create.user_id,
            user_note_number=self.next_id,
            title=note_create.title,
            content=note_create.content,
        )
        self.notes[(note.user_id, note.user_note_number)] = note
        self.notes[note.id] = note
        self.next_id += 1
        return note

    async def get_all_by_user_id(self, user_id):
        return [
            note for key, note in self.notes.items()
            if isinstance(key, tuple) and key[0] == user_id
        ]

    async def get_by_user_note_number(self, user_id, user_note_number):
        return self.notes.get((user_id, user_note_number))

    async def get_by_id(self, note_id):
        return self.notes.get(note_id)

    async def update(self, note, payload):
        if payload.title is not None:
            note.title = payload.title
        if payload.content is not None:
            note.content = payload.content
        return note

    async def delete(self, note):
        self.notes.pop(note.id, None)
        self.notes.pop((note.user_id, note.user_note_number), None)

    async def apply_focus_event(self, note, event, now):
        return note


class FakeTaskRepo:
    def __init__(self):
        self.tasks = {}
        self.next_id = 1

    async def create(self, task_create):
        task = FakeTask(
            id=self.next_id,
            user_id=task_create.user_id,
            title=task_create.title,
            status=task_create.status,
            note_id=task_create.note_id,
            user_task_number=self.next_id,
        )
        self.tasks[task.id] = task
        self.next_id += 1
        return task

    async def get_all_by_note_id(self, note_id):
        return [task for task in self.tasks.values() if task.note_id == note_id]

    async def get_by_id_and_user_id(self, task_id, user_id):
        task = self.tasks.get(task_id)
        if task and task.user_id == user_id:
            return task
        return None

    async def toggle_status(self, task):
        task.status = "done" if task.status == "pending" else "pending"
        return task

    async def delete(self, task):
        self.tasks.pop(task.id, None)

    async def delete_by_note_id(self, note_id):
        to_delete = [task_id for task_id, task in self.tasks.items() if task.note_id == note_id]
        for task_id in to_delete:
            self.tasks.pop(task_id, None)

    async def get_by_user_and_reminder_message_id(self, user_id, message_id):
        return None

    async def mark_done_from_reminder_reply(self, task):
        task.status = "done"
        return task

    async def append_reminder_reply(self, task, text):
        return task

    async def apply_engagement_after_reminder_reply(self, task, text, now):
        return task


def build_service():
    user_repo = FakeUserRepo()
    note_repo = FakeNoteRepo()
    task_repo = FakeTaskRepo()
    service = TelegramService(
        note_repo=note_repo,
        user_repo=user_repo,
        task_repo=task_repo,
    )
    return service, user_repo, note_repo, task_repo


def test_parse_due_date_text_valid():
    result = _parse_due_date_text("2026-04-20")
    assert result == datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)


def test_parse_due_date_text_invalid():
    assert _parse_due_date_text("not-a-date") is None


def test_parse_due_date_text_none():
    assert _parse_due_date_text(None) is None


def test_build_note_title_trims_and_shortens():
    long_text = "   " + "a" * 50 + "   "
    title = TelegramService._build_note_title(long_text)

    assert len(title) == 43
    assert title.endswith("...")


def test_build_note_title_empty_returns_default():
    assert TelegramService._build_note_title("   ") == "Telegram note"

    async def test_get_or_create_user_creates_user():
        service, user_repo, _, _ = build_service()

        user = await service.get_or_create_user(telegram_id=12345, username="u1", full_name="User One")

        assert user.telegram_id == 12345
        assert user.username == "u1"

@pytest.mark.asyncio
async def test_get_or_create_user_returns_existing_user():
    service, user_repo, _, _ = build_service()

    user1 = await service.get_or_create_user(telegram_id=12345, username="u1", full_name="User One")
    user2 = await service.get_or_create_user(telegram_id=12345, username="u2", full_name="Another Name")

    assert user1.id == user2.id
    assert user2.username == "u1"


async def test_get_user_notes_returns_empty_for_unknown_user():
    service, _, _, _ = build_service()

    notes = await service.get_user_notes(99999)

    assert notes == []


async def test_create_task_from_note_returns_none_for_missing_user():
    service, _, _, _ = build_service()

    result = await service.create_task_from_note(
        telegram_id=99999,
        user_note_number=1,
        title="Task",
        description="Desc",
        due_date_text="2026-04-20",
    )

    assert result is None


async def test_create_task_from_note_success():
    service, _, note_repo, task_repo = build_service()

    user = await service.get_or_create_user(telegram_id=12345, username="u1", full_name="User One")
    note = await note_repo.create(type("NoteCreateObj", (), {
        "user_id": user.id,
        "title": "Test note",
        "content": "content",
    })())

    task = await service.create_task_from_note(
        telegram_id=12345,
        user_note_number=note.user_note_number,
        title="My task",
        description="Do something",
        due_date_text="2026-04-20",
    )

    assert task is not None
    assert task.title == "My task"
    assert task.note_id == note.id
    assert task.status == "pending"


async def test_toggle_task_status_success():
    service, _, note_repo, task_repo = build_service()

    user = await service.get_or_create_user(telegram_id=12345, username="u1", full_name="User One")
    note = await note_repo.create(type("NoteCreateObj", (), {
        "user_id": user.id,
        "title": "Test note",
        "content": "content",
    })())
    task = await task_repo.create(type("TaskCreateObj", (), {
        "user_id": user.id,
        "note_id": note.id,
        "title": "Task 1",
        "status": "pending",
    })())

    updated = await service.toggle_task_status(telegram_id=12345, task_id=task.id)

    assert updated is not None
    assert updated.status == "done"


async def test_toggle_task_status_returns_none_for_unknown_user():
    service, _, _, _ = build_service()

    result = await service.toggle_task_status(telegram_id=99999, task_id=1)

    assert result is None


async def test_delete_user_task_success():
    service, _, note_repo, task_repo = build_service()

    user = await service.get_or_create_user(telegram_id=12345, username="u1", full_name="User One")
    note = await note_repo.create(type("NoteCreateObj", (), {
        "user_id": user.id,
        "title": "Test note",
        "content": "content",
    })())
    task = await task_repo.create(type("TaskCreateObj", (), {
        "user_id": user.id,
        "note_id": note.id,
        "title": "Task 1",
        "status": "pending",
    })())

    ok = await service.delete_user_task(telegram_id=12345, task_id=task.id)

    assert ok is True
    assert task_repo.tasks == {}


async def test_update_user_note_success():
    service, _, note_repo, _ = build_service()

    user = await service.get_or_create_user(telegram_id=12345, username="u1", full_name="User One")
    note = await note_repo.create(type("NoteCreateObj", (), {
        "user_id": user.id,
        "title": "Old title",
        "content": "Old content",
    })())

    updated = await service.update_user_note(
        telegram_id=12345,
        user_note_number=note.user_note_number,
        new_content="New content from telegram"
    )

    assert updated is not None
    assert updated.content == "New content from telegram"
    assert updated.title == "New content from telegram"


async def test_delete_user_note_deletes_note_and_tasks():
    service, _, note_repo, task_repo = build_service()

    user = await service.get_or_create_user(telegram_id=12345, username="u1", full_name="User One")
    note = await note_repo.create(type("NoteCreateObj", (), {
        "user_id": user.id,
        "title": "Test note",
        "content": "content",
    })())
    await task_repo.create(type("TaskCreateObj", (), {
        "user_id": user.id,
        "note_id": note.id,
        "title": "Task 1",
        "status": "pending",
    })())

    ok = await service.delete_user_note(telegram_id=12345, user_note_number=note.user_note_number)

    assert ok is True
    assert note_repo.notes == {}
    assert task_repo.tasks == {}