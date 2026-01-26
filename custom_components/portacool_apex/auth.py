from __future__ import annotations

import time
import aiohttp

from .const import API_BASE, SIGNIN_ENDPOINT


class PortaCoolApexAuth:
    """Token manager using PortaCool /user-api/users/signin."""

    def __init__(self, session: aiohttp.ClientSession, username: str, password: str):
        self._session = session
        self._username = username
        self._password = password
        self._access_token: str | None = None
        self._expires_at: float = 0

    async def async_get_token(self) -> str:
        """Return a valid access token; re-login when expired."""
        if self._access_token and time.time() < self._expires_at - 60:
            return self._access_token

        await self._signin()
        return self._access_token  # type: ignore[return-value]

    async def _signin(self) -> None:
        url = f"{API_BASE}{SIGNIN_ENDPOINT}"
        payload = {"username": self._username, "password": self._password}

        async with self._session.post(url, json=payload) as resp:
            resp.raise_for_status()
            data = await resp.json()

        self._access_token = data["access_token"]
        self._expires_at = time.time() + data.get("expires_in", 3600)