"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.websocket import router as ws_router
from app.config import settings
from app.database.connection import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Database initialized")
    yield


app = FastAPI(
    title="Voice Controlled Task Manager API",
    description="Real-time voice assistant backend for task CRUD",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ws_router, tags=["voice"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "voice-task-manager"}


@app.get("/")
async def root():
    return {
        "message": "Voice Controlled Task Manager API",
        "websocket": "/ws/voice",
        "health": "/health",
    }
