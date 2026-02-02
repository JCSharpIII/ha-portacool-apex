from __future__ import annotations

import logging
import time

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PortaCoolApexAPI
from .auth import PortaCoolApexAuth
from .const import (
    CONF_FIREBASE_WEB_API_KEY,
    DOMAIN,
    DP_POWER,
    POLL_INTERVAL,
    POWER_VALUES,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["switch", "select", "sensor"]

# Defaults if options aren't set
DEFAULT_OFFLINE_REFRESH_SECONDS = 60
DEFAULT_POLL_INTERVAL_SECONDS = int(POLL_INTERVAL.total_seconds())


async def async_setup(_: HomeAssistant, __: dict) -> bool:
    return True


def _power_is_off(data: dict) -> bool:
    dps = data.get("datapoints")
    if not isinstance(dps, dict):
        return False
    v = dps.get(DP_POWER)
    if v is None:
        return False
    return str(v) == POWER_VALUES[False]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    session = aiohttp_client.async_get_clientsession(hass)

    auth = PortaCoolApexAuth(
        session=session,
        username=entry.data["username"],
        password=entry.data["password"],
    )

    firebase_key = entry.options.get(CONF_FIREBASE_WEB_API_KEY)
    api = PortaCoolApexAPI(
        session=session,
        auth=auth,
        device_id=entry.data["unique_id"],
        device_type_id=entry.data["device_type_id"],
        firebase_web_api_key=firebase_key,
    )

    # Options
    poll_interval_seconds = int(entry.options.get("poll_interval_seconds", DEFAULT_POLL_INTERVAL_SECONDS))
    offline_refresh_seconds = int(entry.options.get("offline_refresh_seconds", DEFAULT_OFFLINE_REFRESH_SECONDS))

    state_cache: dict[str, object] = {
        "last_network_fetch": 0.0,
        "last_data": {"datapoints": {}, "timer_info": {}, "alerts": []},
        # when set in the future, we bypass offline cache even if power looks off
        "force_refresh_until": 0.0,
    }

    async def _async_update_data():
        try:
            now = time.time()

            last_data = state_cache.get("last_data")
            if not isinstance(last_data, dict):
                last_data = {"datapoints": {}, "timer_info": {}, "alerts": []}

            force_until = float(state_cache.get("force_refresh_until") or 0.0)
            force_refresh = now < force_until

            # If power is OFF and not forcing refresh, throttle network fetches
            if _power_is_off(last_data) and not force_refresh:
                last_fetch = float(state_cache.get("last_network_fetch") or 0.0)
                if now - last_fetch < offline_refresh_seconds:
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
        update_interval=(
            None if poll_interval_seconds <= 0 else __import__("datetime").timedelta(seconds=poll_interval_seconds)
        ),
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "api": api,
        "coordinator": coordinator,
        "entry": entry,
        "state_cache": state_cache,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    return unload_ok