from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from config import Settings


BLOCKED_COMMAND_TOKENS = {
    "rm",
    "mkfs",
    "dd",
    "shutdown",
    "reboot",
    "halt",
    "poweroff",
    "init",
    "iptables",
    "ufw",
}
BLOCKED_COMMAND_FRAGMENTS = {
    "rm -rf /",
    ":(){",
    ">/dev/sda",
    "chmod -R 777 /",
    "chown -R",
    "sudo",
}


class SystemTools:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.workspace = Path.cwd().resolve()
        self.terminal_workdir = self._resolve_workdir(settings.terminal_workdir)

    def open_app(self, name: str) -> dict[str, Any]:
        command = shlex.split(name) if " " in name else [name]
        subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"opened": name}

    def run_terminal(self, command: str) -> dict[str, Any]:
        self._assert_safe_command(command)
        completed = subprocess.run(
            command,
            shell=True,
            cwd=self.terminal_workdir,
            capture_output=True,
            text=True,
            timeout=self.settings.terminal_timeout_seconds,
        )
        return {
            "returncode": completed.returncode,
            "stdout": completed.stdout[-5000:],
            "stderr": completed.stderr[-5000:],
        }

    def read_file(self, path: str) -> dict[str, Any]:
        target = self._safe_path(path)
        return {"path": str(target), "content": target.read_text(encoding="utf-8")[-20000:]}

    def write_file(self, path: str, content: str) -> dict[str, Any]:
        target = self._safe_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"path": str(target), "bytes": len(content.encode("utf-8"))}

    def _safe_path(self, path: str) -> Path:
        target = Path(path).expanduser()
        if not target.is_absolute():
            base = self.terminal_workdir if self.settings.file_access_mode == "full" else self.workspace
            target = base / target
        resolved = target.resolve()
        if self.settings.file_access_mode == "workspace":
            if os.path.commonpath([str(self.workspace), str(resolved)]) != str(self.workspace):
                raise ValueError("File access is limited to the workspace")
            return resolved

        roots = self._allowed_roots()
        if roots and not any(self._is_inside_root(resolved, root) for root in roots):
            raise ValueError(f"File access is limited to: {', '.join(str(root) for root in roots)}")
        return resolved

    def _allowed_roots(self) -> list[Path]:
        raw = self.settings.allowed_file_roots.strip()
        if not raw:
            return []
        return [Path(part).expanduser().resolve() for part in raw.split(os.pathsep) if part.strip()]

    @staticmethod
    def _resolve_workdir(path: Path) -> Path:
        resolved = path.expanduser().resolve()
        return resolved if resolved.exists() else Path.home().resolve()

    @staticmethod
    def _is_inside_root(path: Path, root: Path) -> bool:
        try:
            return os.path.commonpath([str(root), str(path)]) == str(root)
        except ValueError:
            return False

    @staticmethod
    def _assert_safe_command(command: str) -> None:
        lowered = command.lower()
        for fragment in BLOCKED_COMMAND_FRAGMENTS:
            if fragment in lowered:
                raise ValueError(f"Blocked destructive command fragment: {fragment}")
        try:
            tokens = shlex.split(command)
        except ValueError as exc:
            raise ValueError(f"Invalid shell command: {exc}") from exc
        if not tokens:
            raise ValueError("Empty command")
        first = Path(tokens[0]).name.lower()
        if first in BLOCKED_COMMAND_TOKENS:
            raise ValueError(f"Blocked destructive command: {first}")
