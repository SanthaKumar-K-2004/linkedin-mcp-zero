from __future__ import annotations

import asyncio
import random
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

import httpx
import structlog
from platformdirs import user_data_dir

from linkedin_mcp_zero.config.defaults import DATA_DIR_NAME, DEFAULT_LIMIT
from linkedin_mcp_zero.config.settings import Settings
from linkedin_mcp_zero.metrics.store import MetricsStore
from linkedin_mcp_zero.utils.compress import clean_text, compact_dict, truncate

logger = structlog.get_logger()

DAILY_CAPS = {
    "profile_view": 20,
    "people_search": 15,
    "connections": 10,
    "messaging_read": 10,
    "feed_read": 10,
    "notifications": 30,
    "company_people": 15,
}


class BrowserEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._mode = "cdp"
        self._last_used = 0.0
        self._lock = asyncio.Lock()
        self._metrics = MetricsStore(settings)

    async def status(self) -> dict[str, Any]:
        cdp = await self._cdp_status()
        return {
            **cdp,
            "playwright": self._playwright_available(),
            "patchright": self._patchright_available(),
            "patchright_fallback": self.settings.enable_patchright_fallback,
            "connected": self._browser is not None,
            "mode": self._mode if self._browser else None,
            "idle_seconds": round(time.monotonic() - self._last_used, 1) if self._last_used else None,
        }

    async def check_session(self) -> dict[str, Any]:
        ready = await self._ensure_ready()
        if not ready["available"]:
            return ready
        page = await self._page("https://www.linkedin.com/feed/", "feed_read")
        title = await _safe_title(page)
        url = page.url
        logged_in = "login" not in url and "authwall" not in url
        return {
            "available": True,
            "valid": logged_in,
            "url": url,
            "title": title,
            "risk": "browser_readonly_account_risk",
        }

    async def get_my_profile(self) -> dict[str, Any]:
        ready = await self._ensure_ready()
        if not ready["available"]:
            return ready
        page = await self._page("https://www.linkedin.com/in/me/", "profile_view")
        return await self._extract_profile(page, "me")

    async def get_person_profile(self, uname: str) -> dict[str, Any]:
        ready = await self._ensure_ready()
        if not ready["available"]:
            return ready
        profile = uname.strip().rstrip("/")
        if profile.startswith("http"):
            url = profile
            key = profile.rsplit("/", 1)[-1]
        else:
            key = profile.removeprefix("in/")
            url = f"https://www.linkedin.com/in/{key}/"
        page = await self._page(url, "profile_view")
        return await self._extract_profile(page, key)

    async def search_people(
        self,
        kw: str,
        loc: str = "",
        co: str = "",
        limit: int = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        ready = await self._ensure_ready()
        if not ready["available"]:
            return ready
        query = quote_plus(" ".join(part for part in (kw, loc, co) if part))
        page = await self._page(
            f"https://www.linkedin.com/search/results/people/?keywords={query}",
            "people_search",
        )
        people = await _extract_people_links(page, limit)
        return {"items": people, "count": len(people), "source": page.url}

    async def get_my_connections(self, limit: int = 50) -> dict[str, Any]:
        ready = await self._ensure_ready()
        if not ready["available"]:
            return ready
        page = await self._page(
            "https://www.linkedin.com/mynetwork/invite-connect/connections/",
            "connections",
        )
        people = await _extract_people_links(page, limit)
        return {"items": people, "count": len(people), "source": page.url}

    async def get_inbox(self, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        ready = await self._ensure_ready()
        if not ready["available"]:
            return ready
        page = await self._page("https://www.linkedin.com/messaging/", "messaging_read")
        rows = await _extract_text_blocks(
            page,
            "li.msg-conversation-listitem, .msg-conversation-card, a[href*='/messaging/thread/']",
            limit,
            220,
        )
        return {"items": rows, "count": len(rows), "source": page.url}

    async def get_conversation(self, id: str) -> dict[str, Any]:
        ready = await self._ensure_ready()
        if not ready["available"]:
            return ready
        url = id if id.startswith("http") else f"https://www.linkedin.com/messaging/thread/{id}/"
        page = await self._page(url, "messaging_read")
        messages = await _extract_text_blocks(
            page,
            ".msg-s-message-list__event, .msg-s-event-listitem, [data-event-urn]",
            25,
            500,
        )
        return {"items": messages, "count": len(messages), "source": page.url}

    async def get_feed(self, limit: int = 5) -> dict[str, Any]:
        ready = await self._ensure_ready()
        if not ready["available"]:
            return ready
        page = await self._page("https://www.linkedin.com/feed/", "feed_read")
        posts = await _extract_text_blocks(
            page,
            ".feed-shared-update-v2, .occludable-update, article",
            limit,
            700,
        )
        return {"items": posts, "count": len(posts), "source": page.url}

    async def get_notifications(self, limit: int = DEFAULT_LIMIT) -> dict[str, Any]:
        ready = await self._ensure_ready()
        if not ready["available"]:
            return ready
        page = await self._page("https://www.linkedin.com/notifications/", "notifications")
        rows = await _extract_text_blocks(
            page,
            ".nt-card, .notification-item, li",
            limit,
            240,
        )
        return {"items": rows, "count": len(rows), "source": page.url}

    async def get_sidebar_profiles(self) -> dict[str, Any]:
        ready = await self._ensure_ready()
        if not ready["available"]:
            return ready
        page = await self._active_page()
        people = await _extract_people_links(page, 10, selector="aside a[href*='/in/']")
        return {"items": people, "count": len(people), "source": page.url}

    async def get_company_employees(
        self,
        co: str,
        kw: str = "",
        limit: int = 25,
    ) -> dict[str, Any]:
        ready = await self._ensure_ready()
        if not ready["available"]:
            return ready
        slug = _company_slug(co)
        query = f"?keywords={quote_plus(kw)}" if kw else ""
        page = await self._page(
            f"https://www.linkedin.com/company/{slug}/people/{query}",
            "company_people",
        )
        people = await _extract_people_links(page, limit)
        return {"items": people, "count": len(people), "source": page.url}

    async def close_if_idle(self) -> bool:
        if not self._browser or not self._last_used:
            return False
        if time.monotonic() - self._last_used < self.settings.browser_idle_seconds:
            return False
        async with self._lock:
            await self._close_unlocked()
            return True

    async def close(self) -> None:
        async with self._lock:
            await self._close_unlocked()

    async def _ensure_ready(self) -> dict[str, Any]:
        async with self._lock:
            status = await self.status()
            can_fallback = self.settings.enable_patchright_fallback and self._patchright_available()
            if not status.get("available") and not can_fallback:
                return status
            if status.get("available") and not status.get("playwright"):
                return {
                    **status,
                    "available": False,
                    "reason": "Playwright is not installed inside this MCP runtime.",
                    "install": ('uvx --from "mcp-server-linkedin-zero[browser]" mcp-server-linkedin-zero --doctor'),
                }
            if not status.get("available") and can_fallback:
                status = {
                    **status,
                    "available": True,
                    "mode": "patchright",
                    "reason": "CDP unavailable; using explicit higher-risk Patchright fallback.",
                }
            try:
                await self._ensure_browser()
            except Exception as exc:
                return {
                    **status,
                    "available": False,
                    "reason": f"Browser connect failed: {exc}",
                    "start_chrome": "google-chrome --remote-debugging-port=9222",
                }
            return {**status, "available": True, "connected": True}

    async def _ensure_browser(self) -> Any:
        if (
            self._browser
            and self._last_used
            and time.monotonic() - self._last_used >= self.settings.browser_idle_seconds
        ):
            await self._close_unlocked()
        if self._browser:
            self._last_used = time.monotonic()
            return self._browser
        if self.settings.enable_patchright_fallback and not (await self._cdp_status()).get("available"):
            self._mode = "patchright"
            from patchright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            data_dir = Path(self.settings.browser_user_data_dir or user_data_dir(f"{DATA_DIR_NAME}-browser"))
            data_dir.mkdir(parents=True, exist_ok=True)
            self._context = await self._playwright.chromium.launch_persistent_context(
                str(data_dir),
                headless=False,
            )
            self._browser = self._context.browser
        else:
            self._mode = "cdp"
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.connect_over_cdp(self.settings.cdp_url)
        self._last_used = time.monotonic()
        return self._browser

    async def _close_unlocked(self) -> None:
        if self._context:
            with suppress(Exception):
                await self._context.close()
            self._context = None
        if self._browser:
            with suppress(Exception):
                await self._browser.close()
            self._browser = None
        if self._playwright:
            with suppress(Exception):
                await self._playwright.stop()
            self._playwright = None

    async def _page(self, url: str, action_type: str) -> Any:
        await self._pace(action_type)
        browser = await self._ensure_browser()
        context = self._context or (browser.contexts[0] if browser.contexts else await browser.new_context())
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        self._last_used = time.monotonic()
        return page

    async def _active_page(self) -> Any:
        browser = await self._ensure_browser()
        context = self._context or (browser.contexts[0] if browser.contexts else await browser.new_context())
        page = context.pages[0] if context.pages else await context.new_page()
        self._last_used = time.monotonic()
        return page

    async def _extract_profile(self, page: Any, uname: str) -> dict[str, Any]:
        title = await _first_text(page, ["main h1", "h1"])
        headline = await _first_text(
            page,
            [
                ".text-body-medium.break-words",
                ".pv-text-details__left-panel .text-body-medium",
                "main section div.text-body-medium",
            ],
        )
        loc = await _first_text(
            page,
            [".text-body-small.inline.t-black--light.break-words", "main span.text-body-small"],
        )
        about = await _first_text(
            page,
            [
                "section:has(#about) .inline-show-more-text",
                "section:has(#about) .display-flex.ph5",
            ],
            900,
        )
        experience = await _extract_text_blocks(
            page,
            "section:has(#experience) li, #experience ~ div li",
            6,
            260,
        )
        education = await _extract_text_blocks(
            page,
            "section:has(#education) li, #education ~ div li",
            4,
            220,
        )
        return compact_dict(
            {
                "uname": uname,
                "name": title,
                "headline": headline,
                "loc": loc,
                "about": about,
                "exp": experience,
                "edu": education,
                "url": page.url,
                "risk": "browser_readonly_account_risk",
            }
        )

    async def _cdp_status(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=2) as client:
                response = await client.get(f"{self.settings.cdp_url}/json/version")
            if response.status_code >= 400:
                return self._unavailable(f"HTTP {response.status_code}")
            data = response.json()
            return {
                "available": True,
                "risk": "browser_readonly_account_risk",
                "cdp": self.settings.cdp_url,
                "browser": data.get("Browser", ""),
                "websocket": bool(data.get("webSocketDebuggerUrl")),
            }
        except Exception as exc:
            return self._unavailable(str(exc))

    def _unavailable(self, reason: str) -> dict[str, Any]:
        return {
            "available": False,
            "risk": "browser_readonly_account_risk",
            "cdp": self.settings.cdp_url,
            "reason": reason,
            "start_chrome": "google-chrome --remote-debugging-port=9222",
        }

    async def _pace(self, action_type: str) -> None:
        day = datetime.now().date().isoformat()
        cap = DAILY_CAPS.get(action_type, 10)
        current = self._metrics.browser_cap(action_type, day)
        if current >= cap:
            raise RuntimeError(
                f"Daily browser read cap reached for {action_type} ({cap}/day). "
                "This protects your LinkedIn account from high-volume automation."
            )
        await asyncio.sleep(random.uniform(1.5, 4.0))
        self._metrics.increment_browser_cap(action_type, day)

    def _playwright_available(self) -> bool:
        try:
            import playwright.async_api  # noqa: F401
        except ImportError:
            return False
        return True

    def _patchright_available(self) -> bool:
        try:
            import patchright.async_api  # noqa: F401
        except ImportError:
            return False
        return True


async def _safe_title(page: Any) -> str:
    try:
        return clean_text(await page.title())
    except Exception as exc:
        logger.debug("Failed to get page title", error=str(exc))
        return ""


async def _first_text(page: Any, selectors: list[str], max_chars: int = 280) -> str:
    for selector in selectors:
        try:
            text = await page.locator(selector).first().inner_text(timeout=1500)
        except Exception as exc:
            logger.debug("Failed to get first text for selector", selector=selector, error=str(exc))
            continue
        text = truncate(text, max_chars)
        if text:
            return text
    return ""


async def _extract_text_blocks(
    page: Any,
    selector: str,
    limit: int,
    max_chars: int,
) -> list[dict[str, str]]:
    try:
        values = await page.locator(selector).evaluate_all(
            """
            (nodes) => nodes
              .map((node) => ({
                text: (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim(),
                url: node.href || node.querySelector?.('a[href]')?.href || ''
              }))
              .filter((item) => item.text)
            """
        )
    except Exception as exc:
        logger.warning("Failed to extract text blocks", selector=selector, error=str(exc))
        values = []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in values:
        text = truncate(str(item.get("text", "")), max_chars)
        if not text or text in seen:
            continue
        seen.add(text)
        rows.append(compact_dict({"text": text, "url": clean_text(str(item.get("url", "")))}))
        if len(rows) >= limit:
            break
    return rows


async def _extract_people_links(
    page: Any,
    limit: int,
    selector: str = "a[href*='/in/']",
) -> list[dict[str, str]]:
    try:
        values = await page.locator(selector).evaluate_all(
            """
            (nodes) => nodes
              .map((node) => ({
                name: (node.innerText || node.textContent || '').replace(/\\s+/g, ' ').trim(),
                url: node.href || ''
              }))
              .filter((item) => item.url.includes('/in/'))
            """
        )
    except Exception as exc:
        logger.warning("Failed to extract people links", selector=selector, error=str(exc))
        values = []
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in values:
        url = clean_text(str(item.get("url", ""))).split("?")[0]
        if not url or url in seen:
            continue
        seen.add(url)
        name = truncate(str(item.get("name", "")), 120)
        rows.append(compact_dict({"name": name, "url": url}))
        if len(rows) >= limit:
            break
    return rows


def _company_slug(co: str) -> str:
    value = co.strip().lower().removeprefix("company/").strip("/")
    return "-".join(part for part in value.replace("_", "-").split() if part)
