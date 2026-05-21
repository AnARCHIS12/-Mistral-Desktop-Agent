from __future__ import annotations

from pydantic import BaseModel, Field
from fastapi import APIRouter, Request

from api.websocket import websocket_endpoint

router = APIRouter()
router.add_api_websocket_route("/ws", websocket_endpoint)


class GoalRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=4000)


@router.post("/goal")
async def set_goal(payload: GoalRequest, request: Request) -> dict:
    agent = request.app.state.agent
    await agent.set_goal(payload.goal)
    return {"ok": True, "goal": payload.goal}


@router.post("/start")
async def start_agent(request: Request) -> dict:
    agent = request.app.state.agent
    await agent.start()
    return agent.status()


@router.post("/stop")
async def stop_agent(request: Request) -> dict:
    agent = request.app.state.agent
    await agent.stop()
    return agent.status()


@router.get("/status")
async def status(request: Request) -> dict:
    return request.app.state.agent.status()


@router.get("/logs")
async def logs(request: Request, limit: int = 100) -> dict:
    memory = request.app.state.memory
    return {"logs": memory.list_logs(limit=max(1, min(limit, 500)))}
