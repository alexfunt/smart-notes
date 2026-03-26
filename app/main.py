from fastapi import FastAPI

from app.api.v1.auth import router as auth_router
from app.api.v1.health import router as health_router
from app.api.v1.notes import router as notes_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.telegram import router as telegram_router
from app.core.config import settings

app = FastAPI(title=settings.APP_NAME, debug=settings.DEBUG)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(notes_router)
app.include_router(tasks_router)
app.include_router(telegram_router)


@app.get("/")
async def root():
    return {"message": "Smart Notes API is running"}