import os
import sys
from pathlib import Path

import pytest_asyncio
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

os.environ["TEST_DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:55432/smart_notes_test",
)

from app.main import app
from app.core.database import get_db
from app.models.base import Base
from app.models.user import User
from app.models.note import Note
from app.models.task import Task

from app.repositories.user_repo import UserRepository
from app.repositories.note_repo import NoteRepository
from app.repositories.task_repo import TaskRepository

from app.schemas.user import UserCreate
from app.schemas.note import NoteCreate
from app.schemas.task import TaskCreate


TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@127.0.0.1:55432/smart_notes_test",
)

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    future=True,
    poolclass=NullPool,
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://testserver",
    ) as ac:
        yield ac


@pytest_asyncio.fixture
async def created_user(db_session: AsyncSession):
    user_repo = UserRepository(db_session)

    unique_tg_id = int(str(uuid.uuid4().int)[:9])

    user = await user_repo.create(
        UserCreate(
            telegram_id=unique_tg_id,
            username=f"test_user_{unique_tg_id}",
            full_name="Test User",
            email=None,
            timezone="UTC",
        )
    )
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def created_note(db_session: AsyncSession, created_user):
    note_repo = NoteRepository(db_session)

    note = await note_repo.create(
        NoteCreate(
            user_id=created_user.id,
            title="Test note",
            content="This is a test note",
            source="web",
            note_type="plain",
            status="active",
            metadata_json={"tag": "test"},
        )
    )
    await db_session.commit()
    await db_session.refresh(note)
    return note


@pytest_asyncio.fixture
async def created_task(db_session: AsyncSession, created_user, created_note):
    task_repo = TaskRepository(db_session)

    task = await task_repo.create(
        TaskCreate(
            user_id=created_user.id,
            note_id=created_note.id,
            title="Test task",
            description="Task for integration test",
            priority="medium",
            status="pending",
            ai_generated=False,
        )
    )
    await db_session.commit()
    await db_session.refresh(task)
    return task