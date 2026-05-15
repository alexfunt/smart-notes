import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.notes import router as notes_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.telegram import router as telegram_router
from app.core.config import settings

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.services.scheduler_service import check_tasks

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

_cors_origins = [
    origin.strip()
    for origin in (settings.CORS_ORIGINS or "").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _configure_app_logging() -> None:
    """Uvicorn often leaves root at WARNING; ensure app.* INFO lines appear in the console."""
    log = logging.getLogger("app")
    log.setLevel(logging.INFO)
    if log.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    log.addHandler(handler)
    log.propagate = False


_configure_app_logging()

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(notes_router)
app.include_router(tasks_router)
app.include_router(telegram_router)


@app.get("/")
async def root():
    return {"message": "Smart Notes API is running"}

@app.on_event("startup")
async def start_scheduler():
    startup_log = logging.getLogger(__name__)
    startup_log.info(
        "APScheduler started (check_tasks every 1440 min, TASK_REMINDER_INTERVAL_MINUTES=%s)",
        settings.TASK_REMINDER_INTERVAL_MINUTES,
    )
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_tasks, "interval", minutes=5)
    scheduler.start()
    app.state.scheduler = scheduler
