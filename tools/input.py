from __future__ import annotations

from typing import Any


class InputTools:
    def click(self, x: int, y: int) -> dict[str, Any]:
        pyautogui = self._pyautogui()
        pyautogui.click(x=x, y=y)
        return {"clicked": [x, y]}

    def write(self, text: str) -> dict[str, Any]:
        pyautogui = self._pyautogui()
        pyautogui.write(text, interval=0.01)
        return {"typed_chars": len(text)}

    def press(self, key: str) -> dict[str, Any]:
        pyautogui = self._pyautogui()
        pyautogui.press(key)
        return {"pressed": key}

    def hotkey(self, keys: list[str]) -> dict[str, Any]:
        if not keys:
            raise ValueError("keys cannot be empty")
        pyautogui = self._pyautogui()
        pyautogui.hotkey(*keys)
        return {"hotkey": keys}

    @staticmethod
    def _pyautogui():
        import pyautogui

        pyautogui.FAILSAFE = True
        return pyautogui
