from __future__ import annotations

import time

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DP_POWER, POWER_VALUES

COMMAND_GRACE_SECONDS = 2.0


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    coordinator = data["coordinator"]
    async_add_entities([PortacoolAPEXPowerSwitch(api, entry, coordinator)], True)


class PortacoolAPEXPowerSwitch(CoordinatorEntity, SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_icon = "mdi:power"
    _attr_should_poll = False

    def __init__(self, api, entry, coordinator):
        super().__init__(coordinator)
        self._api = api
        self._entry = entry
        self._attr_unique_id = f"{self._api.device_id}_power"
        self._last_cmd_state: bool | None = None
        self._last_cmd_ts: float = 0.0

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

    @property
    def is_on(self) -> bool | None:
        v = self._get_dp(DP_POWER)
        polled = (v == POWER_VALUES[True]) if v is not None else None
        if self._last_cmd_state is not None and (time.time() - self._last_cmd_ts) <= COMMAND_GRACE_SECONDS:
            return self._last_cmd_state
        return polled

    async def async_turn_on(self, **kwargs):
        await self._api.invoke(DP_POWER, POWER_VALUES[True])
        self._last_cmd_state = True
        self._last_cmd_ts = time.time()
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs):
        await self._api.invoke(DP_POWER, POWER_VALUES[False])
        self._last_cmd_state = False
        self._last_cmd_ts = time.time()
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()