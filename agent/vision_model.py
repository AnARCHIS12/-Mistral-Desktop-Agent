from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from config import Settings


class VisionModel:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def analyze(self, image_path: Path, goal: str, ocr_text: str) -> dict[str, Any]:
        if not self.settings.enable_vision_model or not self.settings.mistral_api_key:
            return {"ok": False, "skipped": True, "reason": "vision model disabled or missing api key"}

        payload = {
            "model": self.settings.mistral_vision_model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Analyse cette capture d'ecran pour piloter un ordinateur. "
                                "Retourne uniquement du JSON avec: summary, visible_text, clickable_elements "
                                "(liste de {label, x, y, confidence}), risks, suggested_next_action. "
                                f"Objectif: {goal}\nOCR disponible: {ocr_text[-2500:]}"
                            ),
                        },
                        {"type": "image_url", "image_url": {"url": self._data_url(image_path)}},
                    ],
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.1,
            "max_tokens": 900,
        }
        headers = {
            "Authorization": f"Bearer {self.settings.mistral_api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(self.settings.mistral_api_url, headers=headers, json=payload)
            if response.status_code == 429:
                return {"ok": False, "rate_limited": True, "error": "vision model rate limited"}
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"].get("content") or "{}"
        try:
            analysis = json.loads(content)
        except json.JSONDecodeError:
            analysis = {"summary": content[:1200]}
        analysis["ok"] = True
        analysis["model"] = self.settings.mistral_vision_model
        analysis["usage"] = data.get("usage", {})
        return analysis

    @staticmethod
    def _data_url(path: Path) -> str:
        import base64

        return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")
