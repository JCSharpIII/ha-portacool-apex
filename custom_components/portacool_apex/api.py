from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Any
from urllib.parse import quote

import aiohttp

from .const import (
    API_BASE,
    ALERTS_LATEST_ENDPOINT,
    DEVICES_MY_ENDPOINT,
    FIREBASE_CUSTOM_TOKEN_ENDPOINT,
    FIREBASE_DB,
    FIREBASE_WEB_API_KEY_DEFAULT,
    INVOKE_ACTION_ENDPOINT,
)

_LOGGER = logging.getLogger(__name__)

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=20)

class PortaCoolApexAPI:
    def __init__(
        self,
        session: aiohttp.ClientSession,
        auth,
        device_id: str,
        device_type_id: int,
        firebase_web_api_key: str | None = None,
    ) -> None:
        self._session = session
        self._auth = auth
        self._device_id = device_id
        self._device_type_id = int(device_type_id)
        self._lock = asyncio.Lock()

        # Firebase Identity Toolkit key (public); allow override via OptionsFlow
        self._firebase_web_api_key = (firebase_web_api_key or FIREBASE_WEB_API_KEY_DEFAULT).strip()
        self._verify_custom_token_url = (
            "https://www.googleapis.com/identitytoolkit/v3/relyingparty/"
            f"verifyCustomToken?key={self._firebase_web_api_key}"
        )

        # Cached Firebase identity
        self._fb_id_token: str | None = None
        self._fb_uid: str | None = None
        self._fb_exp: float = 0

    @property
    def device_id(self) -> str:
        return self._device_id

    def set_firebase_web_api_key(self, key: str | None) -> None:
        """Update key at runtime (used when Options change and entry reloads)."""
        self._firebase_web_api_key = (key or FIREBASE_WEB_API_KEY_DEFAULT).strip()
        self._verify_custom_token_url = (
            "https://www.googleapis.com/identitytoolkit/v3/relyingparty/"
            f"verifyCustomToken?key={self._firebase_web_api_key}"
        )
        # Force re-auth next read
        self._fb_id_token = None
        self._fb_uid = None
        self._fb_exp = 0

    async def _headers(self) -> dict[str, str]:
        if self._auth.is_expired():
            await self._auth.refresh()
        return {
            "Authorization": f"Bearer {self._auth.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _get_text(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: aiohttp.ClientTimeout | None = None,
    ) -> str:
        async with self._lock:
            async with self._session.get(
                url,
                headers=headers,
                timeout=timeout or DEFAULT_TIMEOUT,
            ) as resp:
                body = await resp.text()
                if resp.status >= 400:
                    raise aiohttp.ClientResponseError(
                        resp.request_info,
                        resp.history,
                        status=resp.status,
                        message=body,
                        headers=resp.headers,
                    )
                return body

    async def _get_json(self, url: str, headers: dict[str, str] | None = None) -> Any:
        text = await self._get_text(url, headers=headers)
        if text.strip() in ("", "null"):
            return None
        return json.loads(text)

    async def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
        timeout: aiohttp.ClientTimeout | None = None,
    ) -> Any:
        async with self._lock:
            async with self._session.post(
                url,
                json=payload,
                headers=headers,
                timeout=timeout or DEFAULT_TIMEOUT,
            ) as resp:
                body = await resp.text()
                if resp.status >= 400:
                    raise aiohttp.ClientResponseError(
                        resp.request_info,
                        resp.history,
                        status=resp.status,
                        message=body,
                        headers=resp.headers,
                    )
                if body.strip() in ("", "null"):
                    return None
                return json.loads(body)

    async def invoke(self, datapoint_id: int, value: str) -> None:
        payload: dict[str, Any] = {
            "uniqueId": self._device_id,
            "deviceTypeId": self._device_type_id,
            "datapointId": int(datapoint_id),
            "value": str(value),
        }
        async with self._lock:
            async with self._session.post(
                f"{API_BASE}{INVOKE_ACTION_ENDPOINT}",
                headers=await self._headers(),
                json=payload,
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    raise aiohttp.ClientResponseError(
                        resp.request_info,
                        resp.history,
                        status=resp.status,
                        message=body,
                        headers=resp.headers,
                    )

    async def get_devices(self) -> list[dict]:
        """Used by config_flow to discover devices."""
        url = f"{API_BASE}{DEVICES_MY_ENDPOINT}?page=1&pageSize=1000"
        data = await self._get_json(url, headers=await self._headers())
        if isinstance(data, dict):
            items = data.get("items", [])
            return items if isinstance(items, list) else []
        return []

    async def get_alerts_latest(self) -> list[dict]:
        url = f"{API_BASE}{ALERTS_LATEST_ENDPOINT}"
        payload = {"uniqueIds": [self._device_id]}
        data = await self._post_json(url, payload, headers=await self._headers())

        if not isinstance(data, list):
            return []

        for d in data:
            if isinstance(d, dict) and d.get("uniqueId") == self._device_id:
                alerts = d.get("alerts", [])
                return alerts if isinstance(alerts, list) else []
        return []

    # ---------------- Firebase helpers ----------------

    @staticmethod
    def _extract_custom_token(data: Any) -> str:
        if isinstance(data, str) and data.count(".") >= 2:
            return data
        if isinstance(data, dict):
            for k in ("token", "customToken", "custom_token", "firebaseToken", "firebase_custom_token"):
                v = data.get(k)
                if isinstance(v, str) and v.count(".") >= 2:
                    return v
            for v in data.values():
                if isinstance(v, str) and v.count(".") >= 2:
                    return v
        raise RuntimeError("firebase-custom-token did not contain a valid custom token")

    @staticmethod
    def _jwt_payload(token: str) -> dict[str, Any]:
        parts = token.split(".")
        if len(parts) < 2:
            return {}
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        raw = base64.urlsafe_b64decode(payload_b64.encode("utf-8"))
        return json.loads(raw.decode("utf-8"))

    async def _get_firebase_id_token_and_uid(self) -> tuple[str, str]:
        now = time.time()
        if self._fb_id_token and self._fb_uid and now < self._fb_exp - 60:
            return self._fb_id_token, self._fb_uid

        custom_raw = await self._get_json(
            f"{API_BASE}{FIREBASE_CUSTOM_TOKEN_ENDPOINT}",
            headers=await self._headers(),
        )
        custom_token = self._extract_custom_token(custom_raw)

        resp = await self._post_json(
            self._verify_custom_token_url,
            {"returnSecureToken": True, "token": custom_token},
            headers={"Content-Type": "application/json"},
        )
        if not isinstance(resp, dict) or "idToken" not in resp:
            raise RuntimeError(f"verifyCustomToken did not return idToken: {resp}")

        id_token = resp["idToken"]
        payload = self._jwt_payload(id_token)
        uid = payload.get("user_id") or payload.get("sub")
        exp = payload.get("exp")
        if not uid or not exp:
            raise RuntimeError(f"Unable to extract uid/exp from idToken payload: {payload}")

        self._fb_id_token = id_token
        self._fb_uid = str(uid)
        self._fb_exp = float(exp)
        return self._fb_id_token, self._fb_uid

    @staticmethod
    def _parse_datapoints_node(node: Any) -> dict[int, str]:
        out: dict[int, str] = {}
        if node is None:
            return out
        if isinstance(node, dict):
            for k, v in node.items():
                try:
                    dp_id = int(k)
                except Exception:
                    continue
                if isinstance(v, (str, int, float)):
                    out[dp_id] = str(v)
                elif isinstance(v, dict) and "value" in v:
                    out[dp_id] = str(v["value"])
        return out

    async def get_rtdb_state(self) -> tuple[dict[int, str], dict[str, Any]]:
        id_token, uid = await self._get_firebase_id_token_and_uid()
        auth_q = quote(id_token, safe="")

        dp_url = f"{FIREBASE_DB}/users/{uid}/{self._device_id}/datapoints.json?auth={auth_q}"
        timer_url = f"{FIREBASE_DB}/users/{uid}/{self._device_id}/timer.json?auth={auth_q}"

        dp_node = await self._get_json(dp_url)
        timer_node = await self._get_json(timer_url)

        datapoints = self._parse_datapoints_node(dp_node)
        timer_info: dict[str, Any] = timer_node if isinstance(timer_node, dict) else {}
        return datapoints, timer_info