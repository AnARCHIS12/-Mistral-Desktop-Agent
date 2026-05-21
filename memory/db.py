from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


class MemoryDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS actions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    tool TEXT NOT NULL,
                    action_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    ok INTEGER NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS errors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    source TEXT NOT NULL,
                    message TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detail TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    level TEXT NOT NULL,
                    message TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS missions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    goal TEXT NOT NULL,
                    status TEXT NOT NULL,
                    state_json TEXT NOT NULL
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS checkpoints (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    mission_id INTEGER,
                    step INTEGER NOT NULL,
                    progress TEXT NOT NULL,
                    action_json TEXT NOT NULL,
                    result_json TEXT NOT NULL,
                    observation_json TEXT NOT NULL
                )
                """
            )

    def add_action(self, goal: str, action: dict[str, Any], result: dict[str, Any]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO actions(created_at, goal, tool, action_json, result_json, ok)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    self._now(),
                    goal,
                    str(action.get("tool", "")),
                    json.dumps(action, ensure_ascii=True),
                    json.dumps(result, ensure_ascii=True),
                    1 if result.get("ok") else 0,
                ),
            )
        self.add_log("action", f"{action.get('tool')} -> {'ok' if result.get('ok') else 'error'}")

    def add_error(self, source: str, message: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO errors(created_at, source, message) VALUES (?, ?, ?)",
                (self._now(), source, message),
            )
        self.add_log("error", f"{source}: {message}")

    def add_step(self, goal: str, status: str, detail: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO steps(created_at, goal, status, detail) VALUES (?, ?, ?, ?)",
                (self._now(), goal, status, detail),
            )
        self.add_log("step", f"{status}: {detail}")

    def add_log(self, level: str, message: str) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO logs(created_at, level, message) VALUES (?, ?, ?)",
                (self._now(), level, message),
            )

    def recent_actions(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT created_at, goal, tool, action_json, result_json, ok
                FROM actions
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._action_row(row) for row in reversed(rows)]

    def list_logs(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT created_at, level, message FROM logs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def create_mission(self, goal: str, state: dict[str, Any]) -> int:
        now = self._now()
        with self._lock, self._conn:
            cursor = self._conn.execute(
                """
                INSERT INTO missions(created_at, updated_at, goal, status, state_json)
                VALUES (?, ?, ?, ?, ?)
                """,
                (now, now, goal, state.get("status", "planned"), json.dumps(state, ensure_ascii=True)),
            )
            return int(cursor.lastrowid)

    def update_mission(self, mission_id: int, state: dict[str, Any]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE missions SET updated_at = ?, status = ?, state_json = ? WHERE id = ?",
                (self._now(), state.get("status", "running"), json.dumps(state, ensure_ascii=True), mission_id),
            )

    def latest_mission(self) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, created_at, updated_at, goal, status, state_json FROM missions ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["state"] = json.loads(payload.pop("state_json"))
        return payload

    def add_checkpoint(
        self,
        mission_id: int | None,
        step: int,
        progress: str,
        action: dict[str, Any] | None,
        result: dict[str, Any] | None,
        observation: dict[str, Any] | None,
    ) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO checkpoints(created_at, mission_id, step, progress, action_json, result_json, observation_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self._now(),
                    mission_id,
                    step,
                    progress,
                    json.dumps(action or {}, ensure_ascii=True),
                    json.dumps(result or {}, ensure_ascii=True),
                    json.dumps(observation or {}, ensure_ascii=True),
                ),
            )

    def list_checkpoints(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT created_at, mission_id, step, progress, action_json, result_json, observation_json
                FROM checkpoints
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        checkpoints: list[dict[str, Any]] = []
        for row in reversed(rows):
            checkpoints.append(
                {
                    "created_at": row["created_at"],
                    "mission_id": row["mission_id"],
                    "step": row["step"],
                    "progress": row["progress"],
                    "action": json.loads(row["action_json"]),
                    "result": json.loads(row["result_json"]),
                    "observation": json.loads(row["observation_json"]),
                }
            )
        return checkpoints

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _action_row(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "created_at": row["created_at"],
            "goal": row["goal"],
            "tool": row["tool"],
            "action": json.loads(row["action_json"]),
            "result": json.loads(row["result_json"]),
            "ok": bool(row["ok"]),
        }
