from __future__ import annotations

import asyncio
import json
import time
from typing import Any

import httpx

from agent.brain import PLANNER_TOOLS, SYSTEM_PROMPT, build_prompt
from config import Settings


class PlannerError(RuntimeError):
    pass


class MistralRateLimitError(PlannerError):
    def __init__(self, retry_after_seconds: float, message: str) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class MistralPlanner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._last_call_at = 0.0

    async def next_action(
        self,
        goal: str,
        screen_text: str,
        memory: list[dict[str, Any]],
        history: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if not self.settings.mistral_api_key:
            raise PlannerError("MISTRAL_API_KEY is not configured")

        payload = {
            "model": self.settings.mistral_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_prompt(goal, screen_text, memory, history)},
            ],
            "response_format": {"type": "json_object"},
            "tools": PLANNER_TOOLS,
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "temperature": 0.1,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.mistral_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            await self._wait_for_rate_limit_slot()
            response = await client.post(self.settings.mistral_api_url, headers=headers, json=payload)
            self._last_call_at = time.monotonic()
            if response.status_code == 429:
                retry_after = self._retry_after_seconds(response)
                raise MistralRateLimitError(
                    retry_after,
                    f"Mistral rate limit reached. Pausing for {retry_after:.0f}s before retry.",
                )
            response.raise_for_status()
            data = response.json()

        message = data["choices"][0]["message"]
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            call = tool_calls[0]["function"]
            return {
                "tool": call["name"],
                "parameters": json.loads(call.get("arguments") or "{}"),
                "reason": "Action selectionnee par tool calling Mistral",
                "status": "continue",
            }

        content = message.get("content") or "{}"
        try:
            action = json.loads(content)
        except json.JSONDecodeError as exc:
            raise PlannerError(f"Invalid JSON from Mistral: {content[:500]}") from exc

        if not isinstance(action, dict) or "tool" not in action:
            raise PlannerError(f"Invalid action schema from Mistral: {action}")
        action.setdefault("parameters", {})
        action.setdefault("reason", "")
        action.setdefault("status", "continue")
        return action

    async def _wait_for_rate_limit_slot(self) -> None:
        elapsed = time.monotonic() - self._last_call_at
        wait_seconds = self.settings.mistral_min_seconds_between_calls - elapsed
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

    def _retry_after_seconds(self, response: httpx.Response) -> float:
        header = response.headers.get("retry-after")
        if header:
            try:
                return max(float(header), self.settings.mistral_rate_limit_backoff_seconds)
            except ValueError:
                pass
        return self.settings.mistral_rate_limit_backoff_seconds
