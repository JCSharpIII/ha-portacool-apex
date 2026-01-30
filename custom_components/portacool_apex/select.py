from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    DP_POWER,
    DP_TIMER,
    DP_FAN_SPEED,
    DP_PUMP_ENABLE,
    DP_PUMP_MODE,
    DP_PUMP_SPEED,
    POWER_VALUES,
    PUMP_ENABLE_VALUES,
    PUMP_MODE_VALUES,
    TIMER_OPTIONS,
    FAN_MODE_OPTIONS,
    FAN_MODE_LABEL_TO_VALUE,
    FAN_VALUE_TO_LABEL,
    PUMP_MODE_OPTIONS,
)


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    coordinator = data["coordinator"]

    async_add_entities(
        [
            PortacoolAPEXFanModeSelect(api, entry, coordinator),
            PortacoolAPEXTimerSelect(api, entry, coordinator),
            PortacoolAPEXPumpModeSelect(api, entry, coordinator),
        ],
        True,
    )


class _BaseSelect(CoordinatorEntity, SelectEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, api, entry, coordinator):
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

    def _power_is_on(self) -> bool | None:
        v = self._get_dp(DP_POWER)
        return (v == POWER_VALUES[True]) if v is not None else None


class PortacoolAPEXFanModeSelect(_BaseSelect):
    _attr_name = "Fan Mode"
    _attr_icon = "mdi:fan"
    _attr_options = FAN_MODE_OPTIONS

    def __init__(self, api, entry, coordinator):
        super().__init__(api, entry, coordinator)
        self._attr_unique_id = f"{self._api.device_id}_fan_mode"
        self._fallback = "Off"

    @property
    def available(self) -> bool:
        power = self._power_is_on()
        return True if power is None else power

    @property
    def current_option(self):
        v = self._get_dp(DP_FAN_SPEED)
        if v is not None and v in FAN_VALUE_TO_LABEL:
            return FAN_VALUE_TO_LABEL[v]
        return self._fallback

    async def async_select_option(self, option: str) -> None:
        await self._api.invoke(DP_FAN_SPEED, FAN_MODE_LABEL_TO_VALUE[option])
        self._fallback = option
        await self.coordinator.async_request_refresh()


class PortacoolAPEXTimerSelect(_BaseSelect):
    _attr_name = "Timer"
    _attr_icon = "mdi:timer-outline"
    _attr_options = list(TIMER_OPTIONS.keys())

    def __init__(self, api, entry, coordinator):
        super().__init__(api, entry, coordinator)
        self._attr_unique_id = f"{self._api.device_id}_timer"
        self._fallback = "Off"

    @property
    def available(self) -> bool:
        power = self._power_is_on()
        return True if power is None else power

    @property
    def current_option(self):
        v = self._get_dp(DP_TIMER)
        if v is not None:
            for label, api_val in TIMER_OPTIONS.items():
                if str(api_val) == str(v):
                    return label
        return self._fallback

    async def async_select_option(self, option: str) -> None:
        await self._api.invoke(DP_TIMER, TIMER_OPTIONS[option])
        self._fallback = option
        await self.coordinator.async_request_refresh()


class PortacoolAPEXPumpModeSelect(_BaseSelect):
    _attr_name = "Pump Mode"
    _attr_icon = "mdi:water-pump"
    _attr_options = PUMP_MODE_OPTIONS

    def __init__(self, api, entry, coordinator):
        super().__init__(api, entry, coordinator)
        self._attr_unique_id = f"{self._api.device_id}_pump_mode"
        self._fallback = "Off"

    @property
    def available(self) -> bool:
        power = self._power_is_on()
        return True if power is None else power

    @property
    def current_option(self):
        enabled = self._get_dp(DP_PUMP_ENABLE)
        if enabled == PUMP_ENABLE_VALUES[False]:
            return "Off"

        mode_val = self._get_dp(DP_PUMP_MODE)
        if mode_val == PUMP_MODE_VALUES["Eco"]:
            return "Eco"
        if mode_val == PUMP_MODE_VALUES["Max"]:
            return "Max"

        speed = self._get_dp(DP_PUMP_SPEED)
        if speed in {"1", "2", "3", "4", "5"}:
            return speed

        return self._fallback

    async def async_select_option(self, option: str) -> None:
        if option == "Off":
            await self._api.invoke(DP_PUMP_ENABLE, PUMP_ENABLE_VALUES[False])
            self._fallback = "Off"
            await self.coordinator.async_request_refresh()
            return

        # Ensure pump is enabled for any non-Off selection
        await self._api.invoke(DP_PUMP_ENABLE, PUMP_ENABLE_VALUES[True])

        if option in ("Eco", "Max"):
            await self._api.invoke(DP_PUMP_MODE, PUMP_MODE_VALUES[option])
            self._fallback = option
        else:
            # Manual speed 1–5
            await self._api.invoke(DP_PUMP_SPEED, option)
            self._fallback = option

        await self.coordinator.async_request_refresh()