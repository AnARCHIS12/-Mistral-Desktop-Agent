from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import mss
import mss.tools
import pytesseract
from PIL import Image

from config import Settings


class VisionTools:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def screenshot(self) -> dict[str, Any]:
        path = self.settings.screenshot_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            image = sct.grab(monitor)
            mss.tools.to_png(image.rgb, image.size, output=str(path))
        return {
            "path": str(path),
            "width": image.width,
            "height": image.height,
            "base64": self._image_b64(path),
        }

    def ocr(self) -> dict[str, Any]:
        path = self.settings.screenshot_path
        if not path.exists():
            self.screenshot()
        image = Image.open(path)
        text = pytesseract.image_to_string(image)
        return {"path": str(path), "text": text}

    @staticmethod
    def _image_b64(path: Path) -> str:
        payload = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{payload}"
