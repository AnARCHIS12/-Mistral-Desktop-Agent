from __future__ import annotations

import base64
import re
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from config import Settings


class GmailTools:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._service: Any | None = None

    def auth_status(self) -> dict[str, Any]:
        return {
            "credentials_file": str(self.settings.gmail_credentials_file),
            "credentials_exists": self.settings.gmail_credentials_file.exists(),
            "token_file": str(self.settings.gmail_token_file),
            "token_exists": self.settings.gmail_token_file.exists(),
            "scope": self.settings.gmail_scope,
            "modify_enabled": self.settings.gmail_enable_modify,
            "send_enabled": self.settings.gmail_allow_send,
            "delete_enabled": self.settings.gmail_allow_delete,
        }

    def list_recent(self, limit: int = 20, query: str = "in:inbox") -> dict[str, Any]:
        service = self._gmail_service()
        response = service.users().messages().list(userId="me", q=query, maxResults=max(1, min(limit, 50))).execute()
        messages = response.get("messages", [])
        items = [self._message_summary(service, item["id"]) for item in messages]
        return {"count": len(items), "messages": items}

    def ensure_label(self, name: str) -> dict[str, Any]:
        self._assert_modify_allowed()
        service = self._gmail_service()
        existing = self._find_label(service, name)
        if existing:
            return {"label_id": existing["id"], "name": existing["name"], "created": False}
        created = (
            service.users()
            .labels()
            .create(
                userId="me",
                body={
                    "name": name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            .execute()
        )
        return {"label_id": created["id"], "name": created["name"], "created": True}

    def apply_label(self, message_ids: list[str], label_name: str) -> dict[str, Any]:
        self._assert_modify_allowed()
        service = self._gmail_service()
        label = self.ensure_label(label_name)
        ids = [message_id for message_id in message_ids if message_id]
        if not ids:
            return {"modified": 0, "label": label}
        for message_id in ids:
            service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": [label["label_id"]], "removeLabelIds": []},
            ).execute()
        return {"modified": len(ids), "label": label}

    def archive(self, message_ids: list[str]) -> dict[str, Any]:
        self._assert_modify_allowed()
        if not self.settings.gmail_allow_archive:
            raise PermissionError("Gmail archive is disabled by GMAIL_ALLOW_ARCHIVE=false")
        service = self._gmail_service()
        ids = [message_id for message_id in message_ids if message_id]
        for message_id in ids:
            service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"removeLabelIds": ["INBOX"]},
            ).execute()
        return {"archived": len(ids)}

    def send_email(self, to: str, subject: str, body: str) -> dict[str, Any]:
        if not self.settings.gmail_allow_send:
            raise PermissionError("Gmail send is disabled by GMAIL_ALLOW_SEND=false")
        service = self._gmail_service()
        message = EmailMessage()
        message["To"] = to
        message["Subject"] = subject
        message.set_content(body)
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        sent = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        return {"sent": True, "id": sent.get("id")}

    def trash(self, message_ids: list[str]) -> dict[str, Any]:
        if not self.settings.gmail_allow_delete:
            raise PermissionError("Gmail delete/trash is disabled by GMAIL_ALLOW_DELETE=false")
        service = self._gmail_service()
        ids = [message_id for message_id in message_ids if message_id]
        for message_id in ids:
            service.users().messages().trash(userId="me", id=message_id).execute()
        return {"trashed": len(ids)}

    def _gmail_service(self) -> Any:
        if self._service is not None:
            return self._service
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise RuntimeError("Gmail dependencies missing. Run: pip install -r requirements.txt") from exc

        scopes = [self.settings.gmail_scope]
        creds = None
        token_file = self.settings.gmail_token_file
        if token_file.exists():
            creds = Credentials.from_authorized_user_file(str(token_file), scopes)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.settings.gmail_credentials_file.exists():
                    raise FileNotFoundError(
                        f"Missing Gmail OAuth file: {self.settings.gmail_credentials_file}. "
                        "Create an OAuth Desktop client in Google Cloud and save it there."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(str(self.settings.gmail_credentials_file), scopes)
                creds = flow.run_local_server(port=0)
            token_file.parent.mkdir(parents=True, exist_ok=True)
            token_file.write_text(creds.to_json(), encoding="utf-8")
        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def _assert_modify_allowed(self) -> None:
        if not self.settings.gmail_enable_modify:
            raise PermissionError("Gmail modify is disabled by GMAIL_ENABLE_MODIFY=false")

    @staticmethod
    def _find_label(service: Any, name: str) -> dict[str, Any] | None:
        labels = service.users().labels().list(userId="me").execute().get("labels", [])
        for label in labels:
            if label.get("name", "").lower() == name.lower():
                return label
        return None

    @staticmethod
    def _message_summary(service: Any, message_id: str) -> dict[str, Any]:
        message = service.users().messages().get(userId="me", id=message_id, format="metadata").execute()
        headers = {item["name"].lower(): item["value"] for item in message.get("payload", {}).get("headers", [])}
        return {
            "id": message_id,
            "thread_id": message.get("threadId"),
            "label_ids": message.get("labelIds", []),
            "from": headers.get("from", ""),
            "subject": headers.get("subject", ""),
            "date": headers.get("date", ""),
            "snippet": re.sub(r"\s+", " ", message.get("snippet", "")).strip(),
        }
