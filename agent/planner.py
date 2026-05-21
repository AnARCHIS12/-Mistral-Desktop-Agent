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
        self.calls = 0
        self.rate_limits = 0
        self.usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    async def next_action(
        self,
        goal: str,
        screen_text: str,
        memory: list[dict[str, Any]],
        history: list[dict[str, Any]],
        mission: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.settings.mistral_api_key:
            raise PlannerError("MISTRAL_API_KEY is not configured")

        payload = {
            "model": self.settings.mistral_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": build_prompt(goal, screen_text, memory, history, mission)},
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
                self.rate_limits += 1
                retry_after = self._retry_after_seconds(response)
                raise MistralRateLimitError(
                    retry_after,
                    f"Mistral rate limit reached. Pausing for {retry_after:.0f}s before retry.",
                )
            response.raise_for_status()
            data = response.json()
            self.calls += 1
            self._add_usage(data.get("usage") or {})

        message = data["choices"][0]["message"]
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            call = tool_calls[0]["function"]
            arguments = json.loads(call.get("arguments") or "{}")
            return self._normalize_tool_call(call["name"], arguments)

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

    @staticmethod
    def _normalize_tool_call(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(arguments, dict):
            arguments = {}

        nested_parameters = arguments.get("parameters")
        if isinstance(nested_parameters, dict) and arguments.get("tool") in {None, tool_name}:
            parameters = nested_parameters
            reason = str(arguments.get("reason") or "Action selectionnee par tool calling Mistral")
        else:
            parameters = arguments
            reason = "Action selectionnee par tool calling Mistral"

        return {
            "tool": tool_name,
            "parameters": parameters,
            "reason": reason,
            "status": "continue",
        }

    def stats(self) -> dict[str, Any]:
        return {"calls": self.calls, "rate_limits": self.rate_limits, "usage": self.usage}

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

    def _add_usage(self, usage: dict[str, Any]) -> None:
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            try:
                self.usage[key] += int(usage.get(key) or 0)
            except (TypeError, ValueError):
                pass
