from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN, DP_POWER, POWER_VALUES


async def async_setup_entry(hass, entry, async_add_entities):
    api = hass.data[DOMAIN][entry.entry_id]["api"]
    async_add_entities([PortaCoolApexPowerSwitch(api, entry)], True)


class PortaCoolApexPowerSwitch(SwitchEntity):
    _attr_has_entity_name = True
    _attr_name = "Power"
    _attr_icon = "mdi:power"
    _attr_should_poll = False

    def __init__(self, api, entry):
        self._api = api
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_power"
        self._is_on = None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._api.unique_id)},
            manufacturer="PortaCool",
            model=self._entry.data.get("model") or "Apex",
            name=self._entry.data.get("device_name") or "PortaCool Apex",
        )

    @property
    def is_on(self):
        return self._is_on

    async def async_turn_on(self, **kwargs):
        await self._api.invoke(DP_POWER, POWER_VALUES[True])
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        await self._api.invoke(DP_POWER, POWER_VALUES[False])
        self._is_on = False
        self.async_write_ha_state()