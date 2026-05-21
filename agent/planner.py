from __future__ import annotations

import json
from typing import Any

import httpx

from agent.brain import AVAILABLE_TOOLS, SYSTEM_PROMPT, build_prompt
from config import Settings


class PlannerError(RuntimeError):
    pass


class MistralPlanner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

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
            "tools": AVAILABLE_TOOLS,
            "tool_choice": "auto",
            "parallel_tool_calls": False,
            "temperature": 0.1,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.mistral_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(self.settings.mistral_api_url, headers=headers, json=payload)
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
