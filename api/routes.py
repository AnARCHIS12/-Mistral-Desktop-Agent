from __future__ import annotations

from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException, Request

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
    return await agent.start()


@router.post("/stop")
async def stop_agent(request: Request) -> dict:
    agent = request.app.state.agent
    await agent.stop()
    return agent.status()


@router.post("/pause")
async def pause_agent(request: Request) -> dict:
    return await request.app.state.agent.pause()


@router.post("/resume")
async def resume_agent(request: Request) -> dict:
    return await request.app.state.agent.resume()


@router.get("/status")
async def status(request: Request) -> dict:
    return request.app.state.agent.status()


@router.get("/monitoring")
async def monitoring(request: Request) -> dict:
    return {"monitoring": request.app.state.agent.monitoring()}


@router.get("/logs")
async def logs(request: Request, limit: int = 100) -> dict:
    memory = request.app.state.memory
    return {"logs": memory.list_logs(limit=max(1, min(limit, 500)))}


@router.get("/mission")
async def mission(request: Request) -> dict:
    return {"mission": request.app.state.memory.latest_mission()}


@router.get("/checkpoints")
async def checkpoints(request: Request, limit: int = 50) -> dict:
    return {"checkpoints": request.app.state.memory.list_checkpoints(limit=max(1, min(limit, 200)))}


@router.get("/captures")
async def captures(request: Request, limit: int = 50) -> dict:
    return {"captures": request.app.state.memory.list_captures(limit=max(1, min(limit, 200)))}


@router.get("/screenshot")
async def screenshot(request: Request) -> FileResponse:
    path = request.app.state.settings.screenshot_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="No screenshot available")
    return FileResponse(path, media_type="image/png")
