from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, DP_TIMER, TIMER_OPTIONS, DP_FAN_SPEED


async def async_setup_entry(hass, entry, async_add_entities):
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    async_add_entities(
        [
            PortaCoolApexFanSpeedSelect(api, entry),
            PortaCoolApexTimerSelect(api, entry),
        ],
        True,
    )


class _BaseSelect(SelectEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, api, entry):
        self._api = api
        self._entry = entry

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._api.unique_id)},
            manufacturer="PortaCool",
            model=self._entry.data.get("model") or "Apex",
            name=self._entry.data.get("device_name") or "PortaCool Apex",
        )


class PortaCoolApexFanSpeedSelect(_BaseSelect):
    """Discrete fan speed 0–5 (0 = Off)."""

    _attr_name = "Fan Speed"
    _attr_icon = "mdi:fan"
    _attr_options = ["0", "1", "2", "3", "4", "5"]

    def __init__(self, api, entry):
        super().__init__(api, entry)
        self._attr_unique_id = f"{entry.entry_id}_fan_speed"
        self._current = "0"

    @property
    def current_option(self):
        return self._current

    async def async_select_option(self, option: str) -> None:
        # option is already "0".."5"
        await self._api.invoke(DP_FAN_SPEED, option)
        self._current = option
        self.async_write_ha_state()


class PortaCoolApexTimerSelect(_BaseSelect):
    """Auto-off timer."""

    _attr_name = "Timer"
    _attr_icon = "mdi:timer-outline"
    _attr_options = list(TIMER_OPTIONS.keys())

    def __init__(self, api, entry):
        super().__init__(api, entry)
        self._attr_unique_id = f"{entry.entry_id}_timer"
        self._current = "Off"

    @property
    def current_option(self):
        return self._current

    async def async_select_option(self, option: str) -> None:
        await self._api.invoke(DP_TIMER, TIMER_OPTIONS[option])
        self._current = option
        self.async_write_ha_state()