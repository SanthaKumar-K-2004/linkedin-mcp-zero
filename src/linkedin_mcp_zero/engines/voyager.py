from __future__ import annotations

from typing import Any

import structlog
from curl_cffi.requests import AsyncSession

from linkedin_mcp_zero.config.settings import Settings

logger = structlog.get_logger()


class VoyagerEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._session: AsyncSession | None = None  # type: ignore[type-arg]

    async def _get_session(self) -> AsyncSession:  # type: ignore[type-arg]
        if self._session is None:
            self._session = AsyncSession(impersonate="chrome124", timeout=self.settings.timeout_seconds)
        return self._session

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def get_profile(self, uname: str) -> dict[str, Any]:
        if not self.settings.enable_voyager:
            return {
                "available": False,
                "enabled": False,
                "risk": "disabled_private_api_risk",
                "reason": "Voyager is disabled by default to protect user accounts. Use read-only CDP browser tools or pass --enable-voyager.",
                "enable": "Run with --enable-voyager and provide LINKEDIN_MCP_LI_AT to accept responsibility.",
            }
        if not self.settings.li_at:
            return {
                "available": False,
                "enabled": True,
                "risk": "disabled_private_api_risk",
                "reason": "Missing LI_AT session cookie. Provide LINKEDIN_MCP_LI_AT environment variable.",
            }

        clean_uname = uname.strip().rstrip("/").rsplit("/", 1)[-1].removeprefix("in/")
        url = f"https://www.linkedin.com/voyager/api/identity/profiles/{clean_uname}/profileView"

        headers = {
            "Accept": "application/vnd.linkedin.normalized+json+2.1",
            "x-restli-protocol-version": "2.0.0",
            "csrf-token": "ajax:0",
            "Cookie": f'li_at={self.settings.li_at}; JSESSIONID="ajax:0"',
        }

        try:
            session = await self._get_session()
            response = await session.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                profile_elements = data.get("elements", [])
                profile = profile_elements[0] if profile_elements else data.get("profile", {})
                first_name = profile.get("firstName", "")
                last_name = profile.get("lastName", "")
                headline = profile.get("headline", "")
                summary = profile.get("summary", "")
                industry = profile.get("industryName", "")
                geo = profile.get("geoLocationName", "")

                return {
                    "available": True,
                    "enabled": True,
                    "source": "live_voyager_api",
                    "uname": clean_uname,
                    "name": f"{first_name} {last_name}".strip(),
                    "headline": headline,
                    "summary": summary,
                    "industry": industry,
                    "location": geo,
                    "raw_elements": len(profile_elements),
                }
            elif response.status_code in (401, 403):
                logger.warning(
                    "Voyager API authentication rejected", status_code=response.status_code, uname=clean_uname
                )
                return {
                    "available": False,
                    "enabled": True,
                    "error": "authentication_failed",
                    "status_code": response.status_code,
                    "reason": "LinkedIn rejected the provided LI_AT session cookie. The session may have expired.",
                }
            elif response.status_code == 404:
                return {
                    "available": True,
                    "enabled": True,
                    "error": "not_found",
                    "uname": clean_uname,
                    "status_code": 404,
                }
            else:
                logger.warning("Voyager API unexpected status", status_code=response.status_code, uname=clean_uname)
                return {
                    "available": False,
                    "enabled": True,
                    "error": "upstream_error",
                    "status_code": response.status_code,
                }
        except Exception as e:
            logger.error("Failed to query live Voyager API", error=str(e), uname=clean_uname)
            return {
                "available": False,
                "enabled": True,
                "error": "request_exception",
                "detail": str(e),
            }
