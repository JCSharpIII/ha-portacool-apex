from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .auth import PortaCoolApexAuth
from .api import PortaCoolApexAPI

PLATFORMS = ["fan", "switch", "select"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = aiohttp_client.async_get_clientsession(hass)

    auth = PortaCoolApexAuth(
        session=session,
        username=entry.data["username"],
        password=entry.data["password"],
    )

    api = PortaCoolApexAPI(
        session=session,
        auth=auth,
        unique_id=entry.data["unique_id"],
        device_type_id=entry.data["device_type_id"],
    )

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"api": api, "entry": entry}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok