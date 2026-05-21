from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = """
Tu es un agent autonome qui controle un ordinateur via des outils Python.
Tu dois choisir exactement une action par reponse et retourner uniquement un objet JSON valide.

Schema strict:
{
  "tool": "nom_tool",
  "parameters": {},
  "reason": "courte explication",
  "status": "continue|done|error"
}

Regles:
- Utilise status="done" seulement quand l'objectif est accompli.
- Utilise status="error" si l'objectif est impossible ou dangereux.
- Ne propose jamais de commande destructive.
- Ne retourne aucun markdown, aucun commentaire hors JSON.
- Choisis des actions petites, observables et reversibles.
- Pour "ouvre Firefox et cherche X", prefere une seule action search({"query": "X"}), puis termine.
- Evite Google sauf demande explicite, car il affiche souvent des CAPTCHA avec l'automatisation.
- N'utilise pas wmctrl, xdotool ou des commandes de focus fenetre sauf si l'objectif le demande explicitement.
""".strip()


AVAILABLE_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Ouvre une application locale par nom.",
            "parameters": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_terminal",
            "description": "Execute une commande shell non destructive.",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Lit un fichier texte.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Ecrit un fichier texte sur l'ordinateur local, selon la configuration d'acces.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Clique aux coordonnees ecran.",
            "parameters": {
                "type": "object",
                "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
                "required": ["x", "y"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write",
            "description": "Tape du texte au clavier.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press",
            "description": "Appuie sur une touche.",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "hotkey",
            "description": "Appuie sur une combinaison de touches.",
            "parameters": {
                "type": "object",
                "properties": {"keys": {"type": "array", "items": {"type": "string"}}},
                "required": ["keys"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Capture l'ecran et retourne l'image en base64.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ocr",
            "description": "Lit le texte visible a l'ecran.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "open_url",
            "description": "Ouvre une URL avec Playwright.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search",
            "description": "Recherche une requete sur le web avec Playwright.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]

PLANNER_TOOLS: list[dict[str, Any]] = [
    tool for tool in AVAILABLE_TOOLS if tool["function"]["name"] not in {"screenshot", "ocr"}
]


def build_prompt(
    goal: str,
    screen_text: str,
    memory: list[dict[str, Any]],
    history: list[dict[str, Any]],
    mission: dict[str, Any] | None = None,
) -> str:
    return json.dumps(
        {
            "objectif": goal,
            "mission_longue": mission or {},
            "etat_ecran_ocr": screen_text[-6000:],
            "memoire_recente": memory[-10:],
            "historique_actions": history[-10:],
            "outils_disponibles": [tool["function"]["name"] for tool in PLANNER_TOOLS],
            "observation": (
                "La boucle agent capture deja l'ecran et l'OCR avant chaque appel. "
                "Si mission_longue.vision_analysis contient clickable_elements, utilise leurs coordonnees "
                "pour les clics au lieu de deviner. Ne demande pas screenshot ni ocr comme action."
            ),
            "consigne": "Retourne une seule action JSON conforme au schema strict.",
        },
        ensure_ascii=True,
        indent=2,
    )
