from __future__ import annotations

import aiohttp

from .const import (
    API_BASE,
    DEVICES_MY_ENDPOINT,
    INVOKE_ACTION_ENDPOINT,
)
from .auth import PortaCoolApexAuth


class PortaCoolApexAPI:
    """API wrapper for PortaCool device operations."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        auth: PortaCoolApexAuth,
        unique_id: str,
        device_type_id: int,
    ):
        self._session = session
        self._auth = auth
        self.unique_id = unique_id
        self.device_type_id = int(device_type_id)

    async def _headers(self) -> dict:
        token = await self._auth.async_get_token()
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def get_devices(self) -> list[dict]:
        # Match your proven Postman query shape
        url = f"{API_BASE}{DEVICES_MY_ENDPOINT}?page=1&pageSize=1000"
        async with self._session.get(url, headers=await self._headers()) as resp:
            resp.raise_for_status()
            data = await resp.json()
        return data.get("items", [])

    async def invoke(self, datapoint_id: int, value: str) -> None:
        """Invoke a datapoint on the configured device (uniqueId/deviceTypeId)."""
        url = f"{API_BASE}{INVOKE_ACTION_ENDPOINT}"
        payload = {
            "uniqueId": self.unique_id,
            "deviceTypeId": self.device_type_id,
            "datapointId": int(datapoint_id),
            "value": str(value),
        }
        async with self._session.post(url, json=payload, headers=await self._headers()) as resp:
            resp.raise_for_status()