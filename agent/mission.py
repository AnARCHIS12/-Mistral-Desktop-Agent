from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MissionState:
    goal: str
    subtasks: list[dict[str, Any]] = field(default_factory=list)
    current_index: int = 0
    status: str = "planned"
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_goal(cls, goal: str) -> "MissionState":
        return cls(goal=goal, subtasks=_extract_subtasks(goal))

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "MissionState":
        return cls(
            goal=payload.get("goal", ""),
            subtasks=list(payload.get("subtasks") or []),
            current_index=int(payload.get("current_index") or 0),
            status=payload.get("status", "planned"),
            started_at=payload.get("started_at") or datetime.now(timezone.utc).isoformat(),
            updated_at=payload.get("updated_at") or datetime.now(timezone.utc).isoformat(),
            notes=list(payload.get("notes") or []),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "subtasks": self.subtasks,
            "current_index": self.current_index,
            "status": self.status,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "notes": self.notes[-20:],
            "completed": self.completed_count,
            "total": len(self.subtasks),
            "current": self.current_subtask,
        }

    @property
    def completed_count(self) -> int:
        return sum(1 for subtask in self.subtasks if subtask.get("status") == "done")

    @property
    def current_subtask(self) -> dict[str, Any] | None:
        if not self.subtasks:
            return None
        index = min(self.current_index, len(self.subtasks) - 1)
        return self.subtasks[index]

    def add_note(self, note: str) -> None:
        self.notes.append(note)
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def update_after_action(self, action: dict[str, Any], result: dict[str, Any]) -> None:
        if not result.get("ok"):
            self.add_note(f"Echec {action.get('tool')}: {result.get('error', 'unknown')}")
            return
        tool = str(action.get("tool", ""))
        current = self.current_subtask
        if current and _tool_matches_subtask(tool, current.get("text", "")):
            current["status"] = "done"
            current["completed_at"] = datetime.now(timezone.utc).isoformat()
            self.current_index = min(self.current_index + 1, max(len(self.subtasks) - 1, 0))
        if tool == "write_file":
            self._mark_matching("file", "done")
        if tool in {"search", "open_url"}:
            self._mark_matching("search", "done")
        if self.subtasks and self.completed_count == len(self.subtasks):
            self.status = "completed"
        else:
            self.status = "running"
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def _mark_matching(self, kind: str, status: str) -> None:
        for index, subtask in enumerate(self.subtasks):
            if subtask.get("kind") == kind and subtask.get("status") != "done":
                subtask["status"] = status
                subtask["completed_at"] = datetime.now(timezone.utc).isoformat()
                self.current_index = max(self.current_index, min(index + 1, max(len(self.subtasks) - 1, 0)))
                break


def _extract_subtasks(goal: str) -> list[dict[str, Any]]:
    pieces = [
        part.strip(" .\n\t")
        for part in re.split(r"\b(?:puis|ensuite|apres|après|et enfin|, puis)\b|[;]\s*", goal, flags=re.I)
        if part.strip(" .\n\t")
    ]
    if len(pieces) <= 1:
        pieces = _heuristic_pieces(goal)
    subtasks: list[dict[str, Any]] = []
    for index, text in enumerate(pieces, start=1):
        subtasks.append({"id": index, "text": text, "kind": _kind_for_text(text), "status": "pending"})
    return subtasks or [{"id": 1, "text": goal, "kind": "general", "status": "pending"}]


def _heuristic_pieces(goal: str) -> list[str]:
    pieces: list[str] = []
    lowered = goal.lower()
    if any(token in lowered for token in ("cherche", "recherche", "search")):
        pieces.append("Effectuer la recherche demandee")
    if any(token in lowered for token in ("récupère", "recupere", "résumé", "resume", "analyse", "rapport")):
        pieces.append("Lire les informations visibles et preparer la synthese")
    if any(token in lowered for token in ("fichier", ".txt", ".md", "sauvegarde", "enregistre", "crée", "cree")):
        pieces.append("Creer le fichier de sortie demande")
    return pieces


def _kind_for_text(text: str) -> str:
    lowered = text.lower()
    if any(token in lowered for token in ("cherche", "recherche", "search", "ouvre", "site")):
        return "search"
    if any(token in lowered for token in ("fichier", ".txt", ".md", "sauvegarde", "enregistre", "crée", "cree")):
        return "file"
    if any(token in lowered for token in ("résumé", "resume", "analyse", "rapport", "compare", "liste")):
        return "analysis"
    return "general"


def _tool_matches_subtask(tool: str, text: str) -> bool:
    kind = _kind_for_text(text)
    return (
        (kind == "search" and tool in {"search", "open_url", "open_app"})
        or (kind == "file" and tool == "write_file")
        or (kind == "analysis" and tool in {"read_file", "write_file", "ocr"})
    )
