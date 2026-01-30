from __future__ import annotations

import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, POLL_INTERVAL, DP_POWER, POWER_VALUES
from .auth import PortaCoolApexAuth
from .api import PortaCoolApexAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["switch", "select", "sensor"]

# When device power is OFF, only do real network refresh this often:
OFFLINE_REFRESH_SECONDS = 60


async def async_setup(_: HomeAssistant, __: dict) -> bool:
    return True


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
        device_id=entry.data["unique_id"],
        device_type_id=entry.data["device_type_id"],
    )

    state_cache: dict[str, object] = {
        "last_network_fetch": 0.0,
        "last_data": {"datapoints": {}, "timer_info": {}, "alerts": []},
    }

    def _power_is_off(data: dict) -> bool:
        dps = data.get("datapoints")
        if not isinstance(dps, dict):
            return False
        v = dps.get(DP_POWER)
        if v is None:
            return False
        return str(v) == POWER_VALUES[False]

    async def _async_update_data():
        """
        Adaptive polling:
        - If power is OFF: only hit network once per OFFLINE_REFRESH_SECONDS.
          Otherwise return cached data to avoid unnecessary traffic.
        - If power is ON: always hit network on each coordinator tick.
        """
        try:
            now = time.time()
            last_data = state_cache["last_data"]
            assert isinstance(last_data, dict)

            if _power_is_off(last_data):
                last_fetch = float(state_cache["last_network_fetch"])
                if now - last_fetch < OFFLINE_REFRESH_SECONDS:
                    return last_data

            datapoints, timer_info = await api.get_rtdb_state()
            alerts = await api.get_alerts_latest()

            new_data = {"datapoints": datapoints, "timer_info": timer_info, "alerts": alerts}
            state_cache["last_network_fetch"] = now
            state_cache["last_data"] = new_data
            return new_data

        except Exception as err:
            raise UpdateFailed(str(err)) from err

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"{DOMAIN}_{entry.entry_id}_state",
        update_method=_async_update_data,
        update_interval=POLL_INTERVAL,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"api": api, "coordinator": coordinator, "entry": entry}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok