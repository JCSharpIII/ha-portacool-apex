from __future__ import annotations

import time
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DP_POWER, POWER_VALUES

# How long we trust our last commanded state (seconds)
COMMAND_GRACE_SECONDS = 15

# After a command, force real network refresh for this long (seconds)
FORCE_REFRESH_SECONDS = 15


class _BasePortaCoolSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, api, entry) -> None:
        super().__init__(coordinator)
        self._api = api
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._api.device_id)},
            manufacturer="PortaCool",
            model=self._entry.data.get("model") or "Apex",
            name=self._entry.data.get("device_name") or "PortaCool Apex",
        )

    def _get_dp(self, dp_id: int) -> str | None:
        data = self.coordinator.data or {}
        dps = data.get("datapoints") if isinstance(data, dict) else None
        if isinstance(dps, dict) and dp_id in dps:
            return str(dps[dp_id])
        return None

    def _set_dp_optimistic(self, dp_id: int, value: str) -> None:
        """Update coordinator data immediately so UI doesn't flap."""
        data = self.coordinator.data
        if not isinstance(data, dict):
            data = {"datapoints": {}, "timer_info": {}, "alerts": []}

        dps = data.get("datapoints")
        if not isinstance(dps, dict):
            dps = {}

        new_dps = dict(dps)
        new_dps[dp_id] = str(value)

        new_data = dict(data)
        new_data["datapoints"] = new_dps

        # DataUpdateCoordinator helper
        self.coordinator.async_set_updated_data(new_data)

    def _force_refresh_window(self) -> None:
        """Tell __init__.py update loop to bypass offline-cache for a bit."""
        try:
            store = self.hass.data[DOMAIN][self._entry.entry_id]
            cache = store.get("state_cache")
            if isinstance(cache, dict):
                cache["force_refresh_until"] = time.time() + FORCE_REFRESH_SECONDS
        except Exception:
            # If anything is missing, just skip; it's only an optimization.
            return


class PortaCoolPowerSwitch(_BasePortaCoolSwitch):
    _attr_name = "Power"
    _attr_icon = "mdi:power"

    def __init__(self, coordinator, api, entry) -> None:
        super().__init__(coordinator, api, entry)
        self._attr_unique_id = f"{self._api.device_id}_power"

        self._last_cmd_state: bool | None = None
        self._last_cmd_ts: float = 0.0

    @property
    def is_on(self) -> bool | None:
        v = self._get_dp(DP_POWER)
        polled = (v == POWER_VALUES[True]) if v is not None else None

        # If we just issued a command, trust it briefly to avoid UI flapping
        if (
            self._last_cmd_state is not None
            and (time.time() - self._last_cmd_ts) <= COMMAND_GRACE_SECONDS
        ):
            return self._last_cmd_state

        return polled

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._api.invoke(DP_POWER, POWER_VALUES[True])

        self._last_cmd_state = True
        self._last_cmd_ts = time.time()

        # Optimistic update so coordinator doesn't immediately overwrite with cached OFF
        self._set_dp_optimistic(DP_POWER, POWER_VALUES[True])
        self._force_refresh_window()

        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._api.invoke(DP_POWER, POWER_VALUES[False])

        self._last_cmd_state = False
        self._last_cmd_ts = time.time()

        self._set_dp_optimistic(DP_POWER, POWER_VALUES[False])
        self._force_refresh_window()

        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    coordinator = data["coordinator"]

    entities = [
        PortaCoolPowerSwitch(coordinator, api, entry),
    ]

    async_add_entities(entities, True)