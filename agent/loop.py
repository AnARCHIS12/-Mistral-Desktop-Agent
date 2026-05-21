from __future__ import annotations

import asyncio
import base64
import shutil
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from agent.executor import ActionExecutor
from agent.mission import MissionState
from agent.planner import MistralPlanner, MistralRateLimitError, PlannerError
from agent.vision_model import VisionModel
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
        self.vision_model = VisionModel(settings)
        self.executor = ActionExecutor(settings)
        self.vision = VisionTools(settings)
        self.goal: str = ""
        self.running = False
        self.current_action: Optional[dict[str, Any]] = None
        self.progress = "idle"
        self._task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._history: list[dict[str, Any]] = []
        self._mission: MissionState | None = None
        self._mission_id: int | None = None
        self._last_signature: str | None = None
        self._stagnant_count = 0
        self._started_monotonic: float | None = None
        self._current_step = 0
        self._last_vision_analysis: dict[str, Any] | None = None

    async def set_goal(self, goal: str) -> None:
        self.goal = goal.strip()
        self.current_action = None
        self._history = []
        self._mission = MissionState.from_goal(self.goal)
        self._mission_id = self.memory.create_mission(self.goal, self._mission.to_dict())
        self.memory.add_log("goal", self.goal)
        await self._publish("goal", {"goal": self.goal, "mission": self._mission.to_dict()})

    async def start(self) -> dict[str, Any]:
        if self.running:
            return {"ok": True, "message": "Agent deja en cours", **self.status()}
        if not self.goal:
            self.progress = "idle"
            await self._publish("error", {"message": "Aucun objectif defini"})
            return {"ok": False, "message": "Aucun objectif defini", **self.status()}
        self.running = True
        self.progress = "starting"
        self._stop_event.clear()
        self._pause_event.set()
        if self._mission:
            self._mission.status = "running"
            self.memory.update_mission(self._mission_id or 0, self._mission.to_dict())
        self._task = asyncio.create_task(self._run(), name="agent-loop")
        await self._publish("status", self.status())
        return {"ok": True, "message": "Agent demarre", **self.status()}

    async def pause(self) -> dict[str, Any]:
        if self.running:
            self._pause_event.clear()
            self.progress = "paused"
            if self._mission:
                self._mission.status = "paused"
                self.memory.update_mission(self._mission_id or 0, self._mission.to_dict())
            await self._publish("status", self.status())
        return {"ok": True, **self.status()}

    async def resume(self) -> dict[str, Any]:
        self._pause_event.set()
        if self._mission and self.running:
            self._mission.status = "running"
            self.memory.update_mission(self._mission_id or 0, self._mission.to_dict())
        await self._publish("status", self.status())
        return {"ok": True, **self.status()}

    async def stop(self) -> None:
        self._stop_event.set()
        self._pause_event.set()
        if self._task and not self._task.done():
            await self._task
        self.running = False
        self.progress = "stopped"
        if self._mission and self._mission.status not in {"completed"}:
            self._mission.status = "stopped"
            self.memory.update_mission(self._mission_id or 0, self._mission.to_dict())
        await self.executor.close()
        await self._publish("status", self.status())

    def status(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "paused": not self._pause_event.is_set(),
            "goal": self.goal,
            "progress": self.progress,
            "current_action": self.current_action,
            "mission": self._mission.to_dict() if self._mission else None,
            "monitoring": self.monitoring(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    def monitoring(self) -> dict[str, Any]:
        elapsed = int(time.monotonic() - self._started_monotonic) if self._started_monotonic else 0
        return {
            "elapsed_seconds": elapsed,
            "current_step": self._current_step,
            "max_steps": self.settings.max_steps,
            "stagnant_observations": self._stagnant_count,
            "planner": self.planner.stats(),
            "vision_analysis": self._last_vision_analysis,
            "next_subtask": self._mission.current_subtask if self._mission else None,
        }

    async def _run(self) -> None:
        retries: Counter[str] = Counter()
        repeated: Counter[str] = Counter()
        started_at = time.monotonic()
        self._started_monotonic = started_at
        try:
            for step in range(1, self.settings.max_steps + 1):
                self._current_step = step
                if self._stop_event.is_set():
                    break
                if time.monotonic() - started_at > self.settings.max_runtime_seconds:
                    self.progress = "stopped: max runtime reached"
                    break
                await self._pause_event.wait()

                self.progress = f"step {step}/{self.settings.max_steps}: observation"
                try:
                    screenshot = await asyncio.to_thread(self.vision.screenshot)
                except Exception as exc:
                    self.progress = "error: screenshot failed"
                    self.memory.add_error("vision.screenshot", str(exc))
                    await self._publish("error", {"message": f"Screenshot failed: {exc}"})
                    break

                screen_text = await asyncio.to_thread(self.vision.ocr)
                if screen_text.get("error"):
                    self.memory.add_error("vision.ocr", screen_text["error"])
                await self._publish(
                    "observation",
                    {
                        "progress": self.progress,
                        "screenshot": screenshot.get("base64"),
                        "screenshot_backend": screenshot.get("backend"),
                        "screenshot_signature": screenshot.get("signature"),
                        "ocr": screen_text.get("text", "")[-2000:],
                        "ocr_error": screen_text.get("error"),
                        "mission": self._mission.to_dict() if self._mission else None,
                    },
                )
                self._track_stagnation(screenshot.get("signature"))
                important_capture = self._save_important_capture(step, screenshot, "observation")

                vision_analysis = None
                if self.settings.enable_vision_model and step % max(self.settings.vision_every_steps, 1) == 0:
                    vision_analysis = await self.vision_model.analyze(
                        self.settings.screenshot_path,
                        self.goal,
                        screen_text.get("text", ""),
                    )
                    self._last_vision_analysis = vision_analysis
                    if not vision_analysis.get("ok") and not vision_analysis.get("skipped"):
                        self.memory.add_error("vision_model", str(vision_analysis.get("error", "unknown")))

                self.progress = f"step {step}/{self.settings.max_steps}: planning"
                memory = self.memory.recent_actions(limit=12)
                mission_payload = self._mission.to_dict() if self._mission else {}
                if vision_analysis:
                    mission_payload["vision_analysis"] = vision_analysis
                try:
                    action = await self.planner.next_action(
                        self.goal,
                        screen_text.get("text", ""),
                        memory,
                        self._history,
                        mission_payload,
                    )
                except MistralRateLimitError as exc:
                    result = {"ok": False, "error": str(exc), "retry_after_seconds": exc.retry_after_seconds}
                    self.progress = f"rate limited: waiting {exc.retry_after_seconds:.0f}s"
                    self.memory.add_error("planner.rate_limit", str(exc))
                    await self._publish("error", result)
                    retries["planner:rate_limit"] += 1
                    if retries["planner:rate_limit"] >= self.settings.max_retries:
                        self.progress = "stopped: Mistral rate limit"
                        break
                    await asyncio.sleep(exc.retry_after_seconds)
                    continue
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
                if self._mission:
                    self._mission.update_after_action(action, result)
                    self.memory.update_mission(self._mission_id or 0, self._mission.to_dict())
                if step % max(self.settings.checkpoint_every_steps, 1) == 0:
                    self.memory.add_checkpoint(
                        self._mission_id,
                        step,
                        self.progress,
                        action,
                        result,
                        {
                            "screenshot_backend": screenshot.get("backend"),
                            "screenshot_signature": screenshot.get("signature"),
                            "ocr_excerpt": screen_text.get("text", "")[-1000:],
                            "stagnant_count": self._stagnant_count,
                            "important_capture": important_capture,
                            "vision_analysis": vision_analysis,
                        },
                    )
                await self._publish(
                    "result",
                    {
                        "action": action,
                        "result": result,
                        "progress": self.progress,
                        "mission": self._mission.to_dict() if self._mission else None,
                        "monitoring": self.monitoring(),
                    },
                )

                if self._result_satisfies_goal(action, result):
                    self.progress = "done"
                    self.memory.add_step(self.goal, "completed", "Objectif satisfait par l'action executee.")
                    await self._publish("done", {"action": action, "result": result, "progress": self.progress})
                    break

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
        except Exception as exc:
            self.running = False
            self.progress = "error"
            self.memory.add_error("agent", str(exc))
            await self._publish("error", {"message": str(exc)})
        finally:
            self.running = False
            if self._mission and self.progress == "done":
                self._mission.status = "completed"
                self.memory.update_mission(self._mission_id or 0, self._mission.to_dict())
            await self._publish("status", self.status())

    async def _publish(self, event_type: str, payload: dict[str, Any]) -> None:
        event = {"type": event_type, "payload": payload, "status": self.status()}
        await self.websocket_hub.broadcast(event)
        await self.telegram.notify(event)

    @staticmethod
    def _action_key(action: dict[str, Any]) -> str:
        raw = f"{action.get('tool')}:{action.get('parameters')}"
        return base64.b64encode(raw.encode("utf-8")).decode("ascii")

    def _track_stagnation(self, signature: str | None) -> None:
        if not signature:
            return
        if signature == self._last_signature:
            self._stagnant_count += 1
        else:
            self._stagnant_count = 0
            self._last_signature = signature
        if self._stagnant_count >= self.settings.max_stagnant_observations:
            note = f"Stagnation visuelle detectee ({self._stagnant_count} observations similaires). Change de strategie."
            self._history.append({"observation": note})
            if self._mission:
                self._mission.add_note(note)
                self.memory.update_mission(self._mission_id or 0, self._mission.to_dict())

    def _save_important_capture(self, step: int, screenshot: dict[str, Any], reason: str) -> dict[str, Any] | None:
        signature = str(screenshot.get("signature") or "")
        if not signature:
            return None
        important = step == 1 or self._stagnant_count == 0 or self._stagnant_count >= self.settings.max_stagnant_observations
        if not important:
            return None
        source = self.settings.screenshot_path
        if not source.exists():
            return None
        target = self.settings.important_capture_dir / f"mission_{self._mission_id or 0}_step_{step}_{signature}.png"
        try:
            shutil.copy2(source, target)
        except OSError as exc:
            self.memory.add_error("capture", str(exc))
            return None
        payload = {
            "path": str(target),
            "backend": str(screenshot.get("backend") or ""),
            "signature": signature,
            "reason": reason,
        }
        self.memory.add_capture(
            self._mission_id,
            step,
            payload["path"],
            payload["backend"],
            payload["signature"],
            True,
            reason,
        )
        return payload

    def _result_satisfies_goal(self, action: dict[str, Any], result: dict[str, Any]) -> bool:
        if not result.get("ok"):
            return False
        goal = self.goal.lower()
        if self._goal_requires_followup_work(goal):
            return False
        tool = str(action.get("tool", ""))
        if tool == "search" and any(token in goal for token in ("cherche", "recherche", "search", "google")):
            return True
        if tool == "open_url":
            url = str((result.get("result") or {}).get("url", "")).lower()
            return any(token in goal for token in ("cherche", "recherche", "search", "google")) and (
                "search" in url or "duckduckgo.com" in url or "?q=" in url or "&q=" in url
            )
        return False

    @staticmethod
    def _goal_requires_followup_work(goal: str) -> bool:
        followup_tokens = (
            "crée",
            "cree",
            "écris",
            "ecris",
            "fichier",
            ".txt",
            ".md",
            "rapport",
            "résumé",
            "resume",
            "récupère",
            "recupere",
            "analyse",
            "compare",
            "liste",
            "sauvegarde",
            "enregistre",
            "contenant",
        )
        return any(token in goal for token in followup_tokens)
