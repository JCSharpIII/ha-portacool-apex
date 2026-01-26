from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import redact_data

from .const import DOMAIN

REDACT_KEYS = {
    "access_token",
    "refresh_token",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict:
    """Return diagnostics for PortaCool Apex."""
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]

    return {
        "integration": DOMAIN,
        "device": {
            "name": entry.data.get("device_name"),
            "model": entry.data.get("model"),
            "device_id": f'{entry.data["device_id"][:6]}…',
            "device_type_id": entry.data.get("device_type_id"),
        },
        "auth": {
            "token_endpoint": entry.data.get("token_endpoint"),
            "scope": entry.data.get("scope"),
            "expires_at": entry.data.get("expires_at"),
        },
        "config_entry": redact_data(entry.data, REDACT_KEYS),
    }

