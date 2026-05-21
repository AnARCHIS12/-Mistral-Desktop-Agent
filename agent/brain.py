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
- Pour Gmail, prefere les outils gmail_* au pilotage visuel. N'utilise gmail_send_email ou gmail_trash que si l'objectif le demande explicitement.
- Pour Slack, Discord, GitHub, Notion ou webhook, prefere les outils connecteurs directs aux actions navigateur.
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
    {
        "type": "function",
        "function": {
            "name": "gmail_auth_status",
            "description": "Verifie si le connecteur Gmail OAuth est configure.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_list_recent",
            "description": "Liste les messages Gmail recents avec sujet, expediteur, date, labels et extrait.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                    "query": {"type": "string"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_ensure_label",
            "description": "Cree ou retrouve un libelle Gmail.",
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
            "name": "gmail_apply_label",
            "description": "Applique un libelle Gmail a une liste de messages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_ids": {"type": "array", "items": {"type": "string"}},
                    "label_name": {"type": "string"},
                },
                "required": ["message_ids", "label_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_archive",
            "description": "Archive des messages Gmail en retirant le label INBOX. Action modifiante.",
            "parameters": {
                "type": "object",
                "properties": {"message_ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["message_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_send_email",
            "description": "Envoie un email Gmail seulement si GMAIL_ALLOW_SEND=true.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "subject", "body"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gmail_trash",
            "description": "Met des messages Gmail a la corbeille seulement si GMAIL_ALLOW_DELETE=true.",
            "parameters": {
                "type": "object",
                "properties": {"message_ids": {"type": "array", "items": {"type": "string"}}},
                "required": ["message_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "connectors_status",
            "description": "Verifie quels connecteurs externes sont configures: Slack, Discord, GitHub, Notion, HTTP.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "slack_send_message",
            "description": "Envoie un message via un Slack Incoming Webhook.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "webhook_url": {"type": "string"},
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "discord_send_message",
            "description": "Envoie un message via un Discord Webhook.",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "username": {"type": "string"},
                    "webhook_url": {"type": "string"},
                },
                "required": ["content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_create_issue",
            "description": "Cree une issue GitHub dans GITHUB_REPO ou repo explicite.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                    "labels": {"type": "array", "items": {"type": "string"}},
                    "repo": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_list_issues",
            "description": "Liste les issues GitHub d'un depot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "repo": {"type": "string"},
                    "state": {"type": "string", "enum": ["open", "closed", "all"]},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notion_create_page",
            "description": "Cree une page Notion sous NOTION_PARENT_PAGE_ID ou parent explicite.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "content": {"type": "string"},
                    "parent_page_id": {"type": "string"},
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "Appelle une URL HTTP GET et retourne status/body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "headers": {"type": "object", "additionalProperties": {"type": "string"}},
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_post_json",
            "description": "Envoie un JSON a une URL HTTP POST et retourne status/body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string"},
                    "payload": {"type": "object"},
                    "headers": {"type": "object", "additionalProperties": {"type": "string"}},
                },
                "required": ["url"],
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
