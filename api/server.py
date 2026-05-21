from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from agent.loop import AgentLoop
from api.routes import router as api_router
from api.websocket import WebSocketHub
from config import get_settings
from integrations.telegram_bot import TelegramIntegration
from memory.db import MemoryDB


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    memory = MemoryDB(settings.database_path)
    websocket_hub = WebSocketHub()
    telegram = TelegramIntegration(settings)
    agent = AgentLoop(settings=settings, memory=memory, websocket_hub=websocket_hub, telegram=telegram)

    app.state.settings = settings
    app.state.memory = memory
    app.state.websocket_hub = websocket_hub
    app.state.telegram = telegram
    app.state.agent = agent

    await telegram.start(agent)
    yield
    await agent.stop()
    await telegram.stop()
    memory.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    app.mount("/", StaticFiles(directory="web", html=True), name="web")
    return app
