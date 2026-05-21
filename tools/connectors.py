from __future__ import annotations

from typing import Any

import httpx

from config import Settings


class ExternalConnectors:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def status(self) -> dict[str, Any]:
        return {
            "slack": bool(self.settings.slack_webhook_url),
            "discord": bool(self.settings.discord_webhook_url),
            "github": bool(self.settings.github_token and self.settings.github_repo),
            "notion": bool(self.settings.notion_token and self.settings.notion_parent_page_id),
            "http": True,
        }

    def slack_send_message(self, text: str, webhook_url: str | None = None) -> dict[str, Any]:
        url = webhook_url or self.settings.slack_webhook_url
        if not url:
            raise ValueError("Missing SLACK_WEBHOOK_URL")
        response = self._client().post(url, json={"text": text})
        response.raise_for_status()
        return {"sent": True, "status_code": response.status_code}

    def discord_send_message(
        self,
        content: str,
        username: str | None = None,
        webhook_url: str | None = None,
    ) -> dict[str, Any]:
        url = webhook_url or self.settings.discord_webhook_url
        if not url:
            raise ValueError("Missing DISCORD_WEBHOOK_URL")
        payload: dict[str, Any] = {"content": content}
        if username:
            payload["username"] = username
        response = self._client().post(url, json=payload)
        response.raise_for_status()
        return {"sent": True, "status_code": response.status_code}

    def github_create_issue(
        self,
        title: str,
        body: str = "",
        labels: list[str] | None = None,
        repo: str | None = None,
    ) -> dict[str, Any]:
        target_repo = repo or self.settings.github_repo
        if not self.settings.github_token:
            raise ValueError("Missing GITHUB_TOKEN")
        if not target_repo:
            raise ValueError("Missing GITHUB_REPO, expected owner/repo")
        response = self._client().post(
            f"https://api.github.com/repos/{target_repo}/issues",
            headers=self._github_headers(),
            json={"title": title, "body": body, "labels": labels or []},
        )
        response.raise_for_status()
        data = response.json()
        return {"created": True, "number": data.get("number"), "url": data.get("html_url")}

    def github_list_issues(
        self,
        repo: str | None = None,
        state: str = "open",
        limit: int = 20,
    ) -> dict[str, Any]:
        target_repo = repo or self.settings.github_repo
        if not self.settings.github_token:
            raise ValueError("Missing GITHUB_TOKEN")
        if not target_repo:
            raise ValueError("Missing GITHUB_REPO, expected owner/repo")
        response = self._client().get(
            f"https://api.github.com/repos/{target_repo}/issues",
            headers=self._github_headers(),
            params={"state": state, "per_page": max(1, min(limit, 100))},
        )
        response.raise_for_status()
        issues = [
            {
                "number": item.get("number"),
                "title": item.get("title"),
                "state": item.get("state"),
                "url": item.get("html_url"),
            }
            for item in response.json()
            if "pull_request" not in item
        ]
        return {"count": len(issues), "issues": issues}

    def notion_create_page(
        self,
        title: str,
        content: str = "",
        parent_page_id: str | None = None,
    ) -> dict[str, Any]:
        if not self.settings.notion_token:
            raise ValueError("Missing NOTION_TOKEN")
        parent_id = parent_page_id or self.settings.notion_parent_page_id
        if not parent_id:
            raise ValueError("Missing NOTION_PARENT_PAGE_ID")
        response = self._client().post(
            "https://api.notion.com/v1/pages",
            headers={
                "Authorization": f"Bearer {self.settings.notion_token}",
                "Notion-Version": "2022-06-28",
                "Content-Type": "application/json",
            },
            json={
                "parent": {"page_id": parent_id},
                "properties": {"title": {"title": [{"text": {"content": title}}]}},
                "children": self._notion_paragraphs(content),
            },
        )
        response.raise_for_status()
        data = response.json()
        return {"created": True, "id": data.get("id"), "url": data.get("url")}

    def http_get(self, url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        response = self._client().get(url, headers=headers)
        return self._response_payload(response)

    def http_post_json(
        self,
        url: str,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        response = self._client().post(url, json=payload or {}, headers=headers)
        return self._response_payload(response)

    def _client(self) -> httpx.Client:
        return httpx.Client(timeout=self.settings.connector_timeout_seconds, follow_redirects=True)

    def _github_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.github_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    @staticmethod
    def _response_payload(response: httpx.Response) -> dict[str, Any]:
        body: Any
        try:
            body = response.json()
        except ValueError:
            body = response.text[:5000]
        return {"status_code": response.status_code, "ok": response.is_success, "body": body}

    @staticmethod
    def _notion_paragraphs(content: str) -> list[dict[str, Any]]:
        if not content:
            return []
        chunks = [content[index : index + 1800] for index in range(0, min(len(content), 12000), 1800)]
        return [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"type": "text", "text": {"content": chunk}}]},
            }
            for chunk in chunks
        ]
