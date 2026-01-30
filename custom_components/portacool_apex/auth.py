from __future__ import annotations

import time
import aiohttp

from .const import API_BASE, SIGNIN_ENDPOINT


class PortacoolAPEXAuth:
    """
    Auth helper that supports BOTH:
      - New style: async_get_token()  (username/password signin)
      - Legacy style expected by older api.py: is_expired(), refresh(), access_token
    """

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str):
        self._session = session
        self._username = username
        self._password = password

        self._access_token: str | None = None
        self._expires_at: float = 0

    # ---------------------------------------------------------------------
    # New-style API (preferred)
    # ---------------------------------------------------------------------
    async def async_get_token(self) -> str:
        """Return a valid access token; sign in if needed."""
        if self._access_token and time.time() < self._expires_at - 60:
            return self._access_token
        await self._signin()
        return self._access_token  # type: ignore[return-value]

    # ---------------------------------------------------------------------
    # Legacy compatibility for existing api.py
    # ---------------------------------------------------------------------
    @property
    def access_token(self) -> str:
        """Legacy property used by older api.py."""
        if not self._access_token:
            return ""
        return self._access_token

    def is_expired(self) -> bool:
        """Legacy method used by older api.py."""
        if not self._access_token:
            return True
        return time.time() >= self._expires_at - 60

    async def refresh(self) -> None:
        """
        Legacy method used by older api.py.
        We don't have a separate refresh endpoint wired here; re-signin is sufficient.
        """
        await self._signin()

    # ---------------------------------------------------------------------
    # Internal signin
    # ---------------------------------------------------------------------
    async def _signin(self) -> None:
        url = f"{API_BASE}{SIGNIN_ENDPOINT}"
        payload = {"username": self._username, "password": self._password}

        async with self._session.post(url, json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()

        self._access_token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 3600)