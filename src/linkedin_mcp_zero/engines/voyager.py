from __future__ import annotations

from typing import Any

from linkedin_mcp_zero.config.settings import Settings


class VoyagerEngine:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def get_profile(self, uname: str) -> dict[str, Any]:
        if not self.settings.enable_voyager:
            return {
                "available": False,
                "enabled": False,
                "risk": "disabled_private_api_risk",
                "reason": "Voyager is off by default.",
                "enable": ("Run with --enable-voyager and provide LI_AT only if you accept the risk."),
            }
        if not self.settings.li_at:
            return {
                "available": False,
                "enabled": True,
                "risk": "disabled_private_api_risk",
                "reason": "Missing LI_AT session cookie.",
            }
        return {
            "available": False,
            "enabled": True,
            "risk": "disabled_private_api_risk",
            "uname": uname,
            "reason": ("Voyager HTTP implementation is intentionally gated for a later risk-reviewed pass."),
        }
