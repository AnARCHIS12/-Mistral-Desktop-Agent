from __future__ import annotations

import asyncio
import inspect
from typing import Any, Callable

from config import Settings
from tools.browser import BrowserTools
from tools.input import InputTools
from tools.system import SystemTools
from tools.vision import VisionTools


ToolCallable = Callable[..., Any]


class ActionExecutor:
    def __init__(self, settings: Settings) -> None:
        self.system = SystemTools(settings)
        self.input = InputTools()
        self.vision = VisionTools(settings)
        self.browser = BrowserTools(settings)
        self.tools: dict[str, ToolCallable] = {
            "open_app": self.system.open_app,
            "run_terminal": self.system.run_terminal,
            "read_file": self.system.read_file,
            "write_file": self.system.write_file,
            "click": self.input.click,
            "write": self.input.write,
            "press": self.input.press,
            "hotkey": self.input.hotkey,
            "screenshot": self.vision.screenshot,
            "ocr": self.vision.ocr,
            "open_url": self.browser.open_url,
            "search": self.browser.search,
        }

    async def execute(self, action: dict[str, Any]) -> dict[str, Any]:
        tool_name = action.get("tool")
        parameters = action.get("parameters") or {}
        if tool_name not in self.tools:
            return {"ok": False, "error": f"Unknown tool: {tool_name}"}
        func = self.tools[tool_name]
        parameters = self._filter_parameters(func, parameters)
        try:
            if inspect.iscoroutinefunction(func):
                result = await func(**parameters)
            else:
                result = await asyncio.to_thread(func, **parameters)
            return {"ok": True, "tool": tool_name, "result": result}
        except Exception as exc:
            return {"ok": False, "tool": tool_name, "error": str(exc)}

    async def close(self) -> None:
        await self.browser.close()

    @staticmethod
    def _filter_parameters(func: ToolCallable, parameters: dict[str, Any]) -> dict[str, Any]:
        signature = inspect.signature(func)
        if isinstance(parameters.get("parameters"), dict):
            direct_matches = set(parameters) & set(signature.parameters)
            if not direct_matches:
                parameters = parameters["parameters"]
        if any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values()):
            return parameters
        allowed = {
            name
            for name, param in signature.parameters.items()
            if param.kind in {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}
        }
        return {key: value for key, value in parameters.items() if key in allowed}
