from __future__ import annotations

import asyncio
import base64
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from agent.executor import ActionExecutor
from agent.planner import MistralPlanner, PlannerError
from api.websocket import WebSocketHub
from config import Settings
from integrations.telegram_bot import TelegramIntegration
from memory.db import MemoryDB
from tools.vision import VisionTools


class AgentLoop:
    def __init__(
        self,
        settings: Settings,
        memory: MemoryDB,
        websocket_hub: WebSocketHub,
        telegram: TelegramIntegration,
    ) -> None:
        self.settings = settings
        self.memory = memory
        self.websocket_hub = websocket_hub
        self.telegram = telegram
        self.planner = MistralPlanner(settings)
        self.executor = ActionExecutor(settings)
        self.vision = VisionTools(settings)
        self.goal: str = ""
        self.running = False
        self.current_action: Optional[dict[str, Any]] = None
        self.progress = "idle"
        self._task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        self._history: list[dict[str, Any]] = []

    async def set_goal(self, goal: str) -> None:
        self.goal = goal.strip()
        self.memory.add_log("goal", self.goal)
        await self._publish("goal", {"goal": self.goal})

    async def start(self) -> None:
        if self.running:
            return
        if not self.goal:
            await self._publish("error", {"message": "Aucun objectif defini"})
            return
        self.running = True
        self.progress = "starting"
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run(), name="agent-loop")
        await self._publish("status", self.status())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task and not self._task.done():
            await self._task
        self.running = False
        self.progress = "stopped"
        await self.executor.close()
        await self._publish("status", self.status())

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "goal": self.goal,
            "progress": self.progress,
            "current_action": self.current_action,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _run(self) -> None:
        retries: Counter[str] = Counter()
        repeated: Counter[str] = Counter()
        try:
            for step in range(1, self.settings.max_steps + 1):
                if self._stop_event.is_set():
                    break

                self.progress = f"step {step}/{self.settings.max_steps}: observation"
                screenshot = await asyncio.to_thread(self.vision.screenshot)
                screen_text = await asyncio.to_thread(self.vision.ocr)
                await self._publish(
                    "observation",
                    {
                        "progress": self.progress,
                        "screenshot": screenshot.get("base64"),
                        "ocr": screen_text.get("text", "")[-2000:],
                    },
                )

                self.progress = f"step {step}/{self.settings.max_steps}: planning"
                memory = self.memory.recent_actions(limit=12)
                try:
                    action = await self.planner.next_action(
                        self.goal,
                        screen_text.get("text", ""),
                        memory,
                        self._history,
                    )
                except (PlannerError, Exception) as exc:
                    result = {"ok": False, "error": str(exc)}
                    self.memory.add_error("planner", str(exc))
                    await self._publish("error", result)
                    key = f"planner:{exc}"
                    retries[key] += 1
                    if retries[key] >= self.settings.max_retries:
                        self.progress = "stopped: too many planner errors"
                        break
                    await asyncio.sleep(self.settings.loop_delay_seconds)
                    continue

                self.current_action = action
                action_key = self._action_key(action)
                repeated[action_key] += 1
                if repeated[action_key] > self.settings.max_repeated_actions:
                    result = {"ok": False, "error": "Boucle detectee: action repetee trop souvent"}
                    self.memory.add_error(action.get("tool", "unknown"), result["error"])
                    await self._publish("error", result)
                    break

                await self._publish("action", {"action": action, "progress": self.progress})
                if action.get("status") == "done":
                    self.memory.add_step(self.goal, "completed", action.get("reason", ""))
                    self.progress = "done"
                    await self._publish("done", {"action": action, "progress": self.progress})
                    break
                if action.get("status") == "error":
                    self.memory.add_error(action.get("tool", "model"), action.get("reason", "Model error"))
                    self.progress = "error"
                    await self._publish("error", {"action": action, "progress": self.progress})
                    break

                self.progress = f"step {step}/{self.settings.max_steps}: executing {action.get('tool')}"
                result = await self.executor.execute(action)
                self.memory.add_action(self.goal, action, result)
                self._history.append({"action": action, "result": result})
                await self._publish("result", {"action": action, "result": result, "progress": self.progress})

                if not result.get("ok"):
                    key = f"{action.get('tool')}:{result.get('error')}"
                    retries[key] += 1
                    self.memory.add_error(action.get("tool", "unknown"), result.get("error", "Unknown error"))
                    if retries[key] >= self.settings.max_retries:
                        self.progress = "stopped: too many execution errors"
                        break

                await asyncio.sleep(self.settings.loop_delay_seconds)
            else:
                self.progress = "stopped: max steps reached"
        finally:
            self.running = False
            await self._publish("status", self.status())

    async def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {"type": event_type, "payload": payload, "status": self.status()}
        await self.websocket_hub.broadcast(event)
        await self.telegram.notify(event)

    @staticmethod
    def _action_key(action: dict[str, Any]) -> str:
        raw = f"{action.get('tool')}:{action.get('parameters')}"
        return base64.b64encode(raw.encode("utf-8")).decode("ascii")
