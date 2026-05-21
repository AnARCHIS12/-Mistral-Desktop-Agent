from __future__ import annotations

from typing import Any, Optional
from urllib.parse import quote_plus

from playwright.async_api import Browser, Page, async_playwright

from config import Settings


class BrowserTools:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._page: Optional[Page] = None

    async def open_url(self, url: str) -> dict[str, Any]:
        page = await self._get_page()
        await page.goto(url, wait_until="domcontentloaded")
        return {"url": page.url, "title": await page.title()}

    async def search(self, query: str) -> dict[str, Any]:
        engine = self.settings.search_engine.lower().strip()
        encoded = quote_plus(query)
        if engine == "google":
            url = f"https://www.google.com/search?q={encoded}"
        elif engine == "brave":
            url = f"https://search.brave.com/search?q={encoded}"
        else:
            url = f"https://duckduckgo.com/?q={encoded}"
        result = await self.open_url(url)
        result["engine"] = engine if engine in {"google", "brave"} else "duckduckgo"
        result["query"] = query
        return result

    async def close(self) -> None:
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._browser = None
        self._playwright = None
        self._page = None

    async def _get_page(self) -> Page:
        if self._page:
            return self._page
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.settings.browser_headless)
        self._page = await self._browser.new_page(viewport={"width": 1280, "height": 900})
        return self._page
