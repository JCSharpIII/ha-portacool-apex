from __future__ import annotations

import logging
import time
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    # Power / gating
    DP_POWER,
    POWER_VALUES,
    # Fan
    DP_FAN_SPEED,
    FAN_MODE_OPTIONS,
    FAN_MODE_LABEL_TO_VALUE,
    FAN_VALUE_TO_LABEL,
    # Timer
    DP_TIMER,
    TIMER_OPTIONS,
    # Pump (unified)
    DP_PUMP_ENABLE,
    DP_PUMP_MODE,
    DP_PUMP_SPEED,
    PUMP_ENABLE_VALUES,
    PUMP_MODE_VALUES,
    PUMP_MODE_OPTIONS,
    # Water safety
    WATER_ALERT_EMPTY,
)

_LOGGER = logging.getLogger(__name__)

# How long we "trust" the last command to avoid stale cached values flipping UI back
COMMAND_GRACE_SECONDS = 15
# How long we bypass offline throttling after a command
FORCE_REFRESH_SECONDS = 15


class _BasePortaCoolSelect(CoordinatorEntity, SelectEntity):
    """Base class for selects backed by the coordinator."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, api, entry) -> None:
        super().__init__(coordinator)
        self._api = api
        self._entry = entry

        self._last_cmd_ts: float = 0.0
        # dp_id -> last written value
        self._last_cmd_values: dict[int, str] = {}

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

    def _get_alerts(self) -> list[dict]:
        data = self.coordinator.data or {}
        alerts = data.get("alerts") if isinstance(data, dict) else None
        return alerts if isinstance(alerts, list) else []

    def _recent_cmd_value(self, dp_id: int) -> str | None:
        if (time.time() - self._last_cmd_ts) <= COMMAND_GRACE_SECONDS:
            return self._last_cmd_values.get(dp_id)
        return None

    def _set_dp_optimistic(self, updates: dict[int, str]) -> None:
        """Patch coordinator.data['datapoints'] with updated dp values."""
        data = self.coordinator.data
        if not isinstance(data, dict):
            data = {"datapoints": {}, "timer_info": {}, "alerts": []}

        dps = data.get("datapoints")
        if not isinstance(dps, dict):
            dps = {}

        new_dps = dict(dps)
        for k, v in updates.items():
            new_dps[int(k)] = str(v)

        new_data = dict(data)
        new_data["datapoints"] = new_dps

        self.coordinator.async_set_updated_data(new_data)

    def _force_refresh_window(self) -> None:
        """Tell __init__.py coordinator logic to bypass offline throttling briefly."""
        try:
            store = self.hass.data[DOMAIN][self._entry.entry_id]
            cache = store.get("state_cache")
            if isinstance(cache, dict):
                cache["force_refresh_until"] = time.time() + FORCE_REFRESH_SECONDS
        except Exception:
            return

    async def _invoke_many_and_update(self, updates: dict[int, str]) -> None:
        """Invoke one or more datapoints, then optimistic update + force refresh."""
        for dp_id in sorted(updates.keys()):
            await self._api.invoke(dp_id, updates[dp_id])

        self._last_cmd_ts = time.time()
        for dp_id, value in updates.items():
            self._last_cmd_values[int(dp_id)] = str(value)

        self._set_dp_optimistic(updates)
        self._force_refresh_window()

        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    # -------- gating helpers --------

    def _power_is_off(self) -> bool:
        raw = self._get_dp(DP_POWER)
        return raw == POWER_VALUES[False]

    def _water_is_empty(self) -> bool:
        """True if Water Tank Empty alert is active (value != 1)."""
        for a in self._get_alerts():
            if a.get("alertId") == WATER_ALERT_EMPTY:
                try:
                    return int(a.get("value", 1)) != 1
                except Exception:
                    return False
        return False


class PortaCoolFanModeSelect(_BasePortaCoolSelect):
    """Fan Mode (DP13)"""

    _attr_name = "Fan Mode"
    _attr_icon = "mdi:fan"

    def __init__(self, coordinator, api, entry) -> None:
        super().__init__(coordinator, api, entry)
        # IMPORTANT: keep stable unique_id to avoid duplicate entities
        self._attr_unique_id = f"{self._api.device_id}_fan_mode"
        self._attr_options = list(FAN_MODE_OPTIONS)

    @property
    def available(self) -> bool:
        # Grey out when main power is off
        return not self._power_is_off()

    @property
    def current_option(self) -> str | None:
        recent = self._recent_cmd_value(DP_FAN_SPEED)
        if recent is not None:
            return FAN_VALUE_TO_LABEL.get(recent)

        raw = self._get_dp(DP_FAN_SPEED)
        return FAN_VALUE_TO_LABEL.get(raw)

    async def async_select_option(self, option: str) -> None:
        if self._power_is_off():
            return
        value = FAN_MODE_LABEL_TO_VALUE[option]
        await self._invoke_many_and_update({DP_FAN_SPEED: value})


class PortaCoolTimerSelect(_BasePortaCoolSelect):
    """Sleep Timer preset (DP21)"""

    _attr_name = "Timer"
    _attr_icon = "mdi:timer"

    def __init__(self, coordinator, api, entry) -> None:
        super().__init__(coordinator, api, entry)
        # IMPORTANT: keep stable unique_id to avoid duplicate entities
        self._attr_unique_id = f"{self._api.device_id}_sleep_timer"
        self._attr_options = list(TIMER_OPTIONS.keys())

    @property
    def available(self) -> bool:
        # Grey out when main power is off
        return not self._power_is_off()

    @property
    def current_option(self) -> str | None:
        recent = self._recent_cmd_value(DP_TIMER)
        if recent is not None:
            return next((k for k, v in TIMER_OPTIONS.items() if v == recent), None)

        raw = self._get_dp(DP_TIMER)
        return next((k for k, v in TIMER_OPTIONS.items() if v == raw), None)

    async def async_select_option(self, option: str) -> None:
        if self._power_is_off():
            return
        value = TIMER_OPTIONS[option]
        await self._invoke_many_and_update({DP_TIMER: value})


class PortaCoolPumpModeSelect(_BasePortaCoolSelect):
    """Pump Mode (unified)

    Options: Off, Eco, 1,2,3,4,5, Max

    Uses:
      DP27 Pump Enable: 1=Off, 2=On
      DP26 Pump Mode:   1=Eco, 2=Max, 3=Manual
      DP14 Pump Speed:  0..5 (manual speeds)
    """

    _attr_name = "Pump Mode"
    _attr_icon = "mdi:water-pump"

    def __init__(self, coordinator, api, entry) -> None:
        super().__init__(coordinator, api, entry)
        # IMPORTANT: keep stable unique_id to avoid duplicate entities
        self._attr_unique_id = f"{self._api.device_id}_pump_mode"
        self._attr_options = list(PUMP_MODE_OPTIONS)

    @property
    def available(self) -> bool:
        # Grey out when main power is off
        if self._power_is_off():
            return False

        # Grey out when tank is empty AND pump is already Off (safe state).
        # If pump is somehow ON while empty, keep it available so the user can force Off.
        if self._water_is_empty():
            enable = self._get_dp(DP_PUMP_ENABLE)
            return enable != PUMP_ENABLE_VALUES[False]
        return True

    def _pump_enable_raw(self) -> str | None:
        recent = self._recent_cmd_value(DP_PUMP_ENABLE)
        if recent is not None:
            return recent
        return self._get_dp(DP_PUMP_ENABLE)

    def _pump_mode_raw(self) -> str | None:
        recent = self._recent_cmd_value(DP_PUMP_MODE)
        if recent is not None:
            return recent
        return self._get_dp(DP_PUMP_MODE)

    def _pump_speed_raw(self) -> str | None:
        recent = self._recent_cmd_value(DP_PUMP_SPEED)
        if recent is not None:
            return recent
        return self._get_dp(DP_PUMP_SPEED)

    @property
    def current_option(self) -> str | None:
        enable = self._pump_enable_raw()
        if enable == PUMP_ENABLE_VALUES[False]:
            return "Off"

        mode = self._pump_mode_raw()
        if mode == PUMP_MODE_VALUES.get("Eco"):
            return "Eco"
        if mode == PUMP_MODE_VALUES.get("Max"):
            return "Max"

        speed = self._pump_speed_raw()
        if speed in ("1", "2", "3", "4", "5"):
            return speed

        if mode == PUMP_MODE_VALUES.get("Manual"):
            return "1"
        return None

    async def async_select_option(self, option: str) -> None:
        if self._power_is_off():
            return

        # SAFETY: if tank is empty, silently ignore any attempt to turn pump ON.
        # (The entity will be disabled when the pump is already Off.)
        if option != "Off" and self._water_is_empty():
            _LOGGER.warning("Pump Mode change ignored: water tank is empty (requested %s)", option)
            return

        updates: dict[int, str] = {}

        if option == "Off":
            updates[DP_PUMP_ENABLE] = PUMP_ENABLE_VALUES[False]
            updates[DP_PUMP_SPEED] = "0"
            await self._invoke_many_and_update(updates)
            return

        updates[DP_PUMP_ENABLE] = PUMP_ENABLE_VALUES[True]

        if option == "Eco":
            updates[DP_PUMP_MODE] = PUMP_MODE_VALUES["Eco"]
            updates[DP_PUMP_SPEED] = "0"
            await self._invoke_many_and_update(updates)
            return

        if option == "Max":
            updates[DP_PUMP_MODE] = PUMP_MODE_VALUES["Max"]
            updates[DP_PUMP_SPEED] = "0"
            await self._invoke_many_and_update(updates)
            return

        if option in ("1", "2", "3", "4", "5"):
            updates[DP_PUMP_MODE] = PUMP_MODE_VALUES["Manual"]
            updates[DP_PUMP_SPEED] = option
            await self._invoke_many_and_update(updates)
            return

        raise ValueError(f"Unsupported pump option: {option}")


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    coordinator = data["coordinator"]

    entities = [
        PortaCoolFanModeSelect(coordinator, api, entry),
        PortaCoolPumpModeSelect(coordinator, api, entry),
        PortaCoolTimerSelect(coordinator, api, entry),
    ]

    async_add_entities(entities, True)