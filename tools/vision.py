from __future__ import annotations

import base64
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

import mss
import mss.tools
import pytesseract
from PIL import Image, ImageStat

from config import Settings


class VisionTools:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def screenshot(self) -> dict[str, Any]:
        path = self.settings.screenshot_path
        path.parent.mkdir(parents=True, exist_ok=True)
        backend = self.settings.screenshot_backend.lower().strip()

        if backend != "mss":
            external = self._screenshot_external(path, preferred=backend if backend != "auto" else "")
            if external and not self._is_black_image(path):
                return self._screenshot_result(path, external)

        with mss.mss() as sct:
            monitor = sct.monitors[1]
            image = sct.grab(monitor)
            mss.tools.to_png(image.rgb, image.size, output=str(path))

        if self._is_black_image(path):
            external = self._screenshot_external(path)
            if external and not self._is_black_image(path):
                return self._screenshot_result(path, external)

        return self._screenshot_result(path, "mss")

    def ocr(self) -> dict[str, Any]:
        path = self.settings.screenshot_path
        if not path.exists():
            self.screenshot()
        image = Image.open(path)
        try:
            text = pytesseract.image_to_string(image)
        except pytesseract.pytesseract.TesseractNotFoundError:
            return {
                "path": str(path),
                "text": "",
                "ok": False,
                "error": "Tesseract OCR is not installed. Install tesseract-ocr to enable OCR.",
            }
        return {"path": str(path), "text": text, "ok": True}

    @staticmethod
    def _image_b64(path: Path) -> str:
        payload = base64.b64encode(path.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{payload}"

    @staticmethod
    def _screenshot_result(path: Path, backend: str) -> dict[str, Any]:
        image = Image.open(path)
        return {
            "path": str(path),
            "width": image.width,
            "height": image.height,
            "backend": backend,
            "base64": VisionTools._image_b64(path),
        }

    @staticmethod
    def _is_black_image(path: Path) -> bool:
        if not path.exists() or path.stat().st_size == 0:
            return True
        image = Image.open(path).convert("RGB")
        stat = ImageStat.Stat(image.resize((64, 64)))
        mean = sum(stat.mean) / 3
        extrema = image.getextrema()
        max_channel = max(high for _low, high in extrema)
        return mean < 2 and max_channel < 8

    def _screenshot_external(self, path: Path, preferred: str = "") -> str | None:
        backends = [preferred] if preferred else []
        if os.environ.get("WAYLAND_DISPLAY"):
            backends.extend(["gnome-screenshot", "grim", "spectacle"])
        backends.extend(["gnome-screenshot", "grim", "spectacle", "scrot"])

        seen: set[str] = set()
        for backend in backends:
            if not backend or backend in seen:
                continue
            seen.add(backend)
            if self._run_screenshot_backend(backend, path):
                return backend
        return None

    @staticmethod
    def _run_screenshot_backend(backend: str, path: Path) -> bool:
        commands = {
            "gnome-screenshot": ["gnome-screenshot", "-f", str(path)],
            "grim": ["grim", str(path)],
            "spectacle": ["spectacle", "-b", "-n", "-o", str(path)],
            "scrot": ["scrot", str(path)],
        }
        command = commands.get(backend)
        if not command:
            return False
        if shutil.which(command[0]) and VisionTools._run_command(command):
            return True
        if shutil.which("flatpak-spawn"):
            return VisionTools._run_command(["flatpak-spawn", "--host", *command])
        return False

    @staticmethod
    def _run_command(command: list[str]) -> bool:
        try:
            completed = subprocess.run(command, capture_output=True, text=True, timeout=10)
        except Exception:
            return False
        output_path = Path(command[-1])
        return completed.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0
