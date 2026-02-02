from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import redact_data

from .const import DOMAIN

# Redact any sensitive config entry fields and anything token-like
REDACT_KEYS = {
    "username",
    "password",
    "access_token",
    "refresh_token",
    "id_token",
    "token",
    "auth",
    "authorization",
    "firebase_web_api_key",  # not secret, but keep it out of diagnostics by default
}


def _mask(s: Any, keep: int = 6) -> str | None:
    if not isinstance(s, str) or not s:
        return None
    if len(s) <= keep:
        return f"{s}…"
    return f"{s[:keep]}…"


def _safe_coordinator_snapshot(data: Any) -> dict[str, Any]:
    """
    Return a safe-to-share snapshot of coordinator data.
    - Includes datapoints (as-is) because they are device telemetry, not credentials.
    - Includes timer_info and alerts, but prunes/keeps only what’s useful.
    """
    if not isinstance(data, dict):
        return {"data_type": str(type(data))}

    datapoints = data.get("datapoints")
    timer_info = data.get("timer_info")
    alerts = data.get("alerts")

    # Alerts can be large; keep only active + a small sample of inactive
    safe_alerts: list[dict[str, Any]] = []
    if isinstance(alerts, list):
        active = []
        inactive = []
        for a in alerts:
            if not isinstance(a, dict):
                continue
            try:
                is_active = int(a.get("value", 1)) != 1
            except Exception:
                is_active = False
            (active if is_active else inactive).append(
                {
                    "alertId": a.get("alertId"),
                    "alertName": a.get("alertName"),
                    "alertType": a.get("alertType"),
                    "value": a.get("value"),
                    "timestamp": a.get("timestamp"),
                }
            )

        safe_alerts = active + inactive[:5]

    return {
        "datapoints": datapoints if isinstance(datapoints, dict) else None,
        "timer_info": timer_info if isinstance(timer_info, dict) else None,
        "alerts_sample": safe_alerts,
        "alerts_total": len(alerts) if isinstance(alerts, list) else None,
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for PortaCool Apex."""

    store = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = store.get("coordinator")

    # You store device unique id in entry.data["unique_id"]
    unique_id = entry.data.get("unique_id")
    device_type_id = entry.data.get("device_type_id")

    diag: dict[str, Any] = {
        "integration": DOMAIN,
        "entry": {
            "entry_id": entry.entry_id,
            "title": entry.title,
            "domain": entry.domain,
            "version": entry.version,
        },
        "device": {
            "device_name": entry.data.get("device_name"),
            "model": entry.data.get("model"),
            "unique_id": _mask(unique_id),
            "device_type_id": device_type_id,
        },
        "options": redact_data(dict(entry.options), REDACT_KEYS),
        "config_entry_data": redact_data(dict(entry.data), REDACT_KEYS),
    }

    if coordinator is not None:
        try:
            diag["coordinator"] = {
                "last_update_success": getattr(coordinator, "last_update_success", None),
                "last_exception": str(getattr(coordinator, "last_exception", None))
                if getattr(coordinator, "last_exception", None)
                else None,
                "data_snapshot": _safe_coordinator_snapshot(getattr(coordinator, "data", None)),
            }
        except Exception as err:
            diag["coordinator"] = {"error": str(err)}

    return diag