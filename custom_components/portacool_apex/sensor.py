from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import UnitOfElectricPotential, UnitOfTemperature, UnitOfTime
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ALERT_CATEGORIES

DP_EXIT_TEMP = 3
DP_AMBIENT_TEMP = 4
DP_VOLTAGE_A = 31
DP_VOLTAGE_B = 32


def _category_key(alert_id: str) -> str | None:
    if not isinstance(alert_id, str) or "-" not in alert_id:
        return None
    return alert_id.split("-", 1)[0]


def _is_active(alert: dict) -> bool:
    try:
        return int(alert.get("value", 1)) != 1
    except Exception:
        return False


def _severity(active_alerts: list[dict]) -> str:
    if any(a.get("alertType") == "Error" for a in active_alerts):
        return "Error"
    if any(a.get("alertType") == "Warning" for a in active_alerts):
        return "Warning"
    return "OK"


def _parse_timerexpiry(ts: Any) -> datetime | None:
    """
    Parses TimerExpiry like: 2026-01-29T06:54:30.3051500Z
    Handles 7-digit fractional seconds by trimming to 6.
    """
    if not isinstance(ts, str) or not ts:
        return None

    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    # Normalize fractional seconds to 6 digits for datetime.fromisoformat
    if "." in s:
        head, tail = s.split(".", 1)
        if "+" in tail:
            frac, rest = tail.split("+", 1)
            frac = (frac + "000000")[:6]
            s = f"{head}.{frac}+{rest}"
        else:
            frac = (tail + "000000")[:6]
            s = f"{head}.{frac}"

    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


class _BasePortaCoolSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, api, entry):
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

    def _get_alerts(self) -> list[dict]:
        data = self.coordinator.data or {}
        alerts = data.get("alerts") if isinstance(data, dict) else None
        return alerts if isinstance(alerts, list) else []

    def _timer_info(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        ti = data.get("timer_info") if isinstance(data, dict) else None
        return ti if isinstance(ti, dict) else {}


class PortaCoolTimerRemainingSensor(_BasePortaCoolSensor):
    """
    Professional countdown:
    - Polling provides TimerExpiry (authoritative)
    - We tick locally every 1s to update remaining time without extra network traffic
    """
    _attr_name = "Timer Remaining"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_icon = "mdi:timer-sand"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator, api, entry)
        self._attr_unique_id = f"{self._api.device_id}_timer_remaining"

        self._expiry_raw: str | None = None
        self._expiry_dt: datetime | None = None
        self._sleep_timer: Any = None
        self._unsub_tick = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        # Seed values from current coordinator data
        self._refresh_from_coordinator()

        # Subscribe to coordinator updates (so when TimerExpiry changes, countdown resets)
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))

        # Local 1-second tick
        self._unsub_tick = async_track_time_interval(self.hass, self._tick, timedelta(seconds=1))
        self.async_on_remove(self._unsub_tick)

    def _handle_coordinator_update(self) -> None:
        # Called when coordinator refreshes
        self._refresh_from_coordinator()
        self.async_write_ha_state()

    def _refresh_from_coordinator(self) -> None:
        ti = self._timer_info()
        self._sleep_timer = ti.get("SleepTimer")
        self._expiry_raw = ti.get("TimerExpiry")
        self._expiry_dt = _parse_timerexpiry(self._expiry_raw)

    async def _tick(self, _now: datetime) -> None:
        # Only update our entity; no network calls
        self.async_write_ha_state()

    @property
    def native_value(self):
        # If expiry missing -> 0
        if not self._expiry_dt:
            return 0
        now = datetime.now(timezone.utc)
        remaining = int((self._expiry_dt - now).total_seconds())
        return max(0, remaining)

    @property
    def extra_state_attributes(self):
        remaining = int(self.native_value or 0)
        hrs = remaining // 3600
        mins = (remaining % 3600) // 60
        secs = remaining % 60
        return {
            "SleepTimer": self._sleep_timer,
            "TimerExpiry": self._expiry_raw,
            "TimerExpiryUtc": self._expiry_dt.isoformat() if self._expiry_dt else None,
            "remaining_hms": f"{hrs:01d}:{mins:02d}:{secs:02d}",
        }


class PortaCoolExitTemperatureSensor(_BasePortaCoolSensor):
    _attr_name = "Exit Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_device_class = "temperature"
    _attr_state_class = "measurement"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator, api, entry)
        self._attr_unique_id = f"{self._api.device_id}_exit_temp"

    @property
    def native_value(self):
        raw = self._get_dp(DP_EXIT_TEMP)
        if raw is None:
            return None
        try:
            return int(round(float(raw)))
        except Exception:
            return None

    @property
    def extra_state_attributes(self):
        return {"raw": self._get_dp(DP_EXIT_TEMP)}


class PortaCoolAmbientTemperatureSensor(_BasePortaCoolSensor):
    _attr_name = "Ambient Temperature"
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_device_class = "temperature"
    _attr_state_class = "measurement"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator, api, entry)
        self._attr_unique_id = f"{self._api.device_id}_ambient_temp"

    @property
    def native_value(self):
        raw = self._get_dp(DP_AMBIENT_TEMP)
        if raw is None:
            return None
        try:
            return int(round(float(raw)))
        except Exception:
            return None

    @property
    def extra_state_attributes(self):
        return {"raw": self._get_dp(DP_AMBIENT_TEMP)}


class PortaCoolInputVoltageSensor(_BasePortaCoolSensor):
    _attr_name = "Input Voltage"
    _attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
    _attr_device_class = "voltage"
    _attr_state_class = "measurement"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator, api, entry)
        self._attr_unique_id = f"{self._api.device_id}_input_voltage"

    @property
    def native_value(self):
        raw = self._get_dp(DP_VOLTAGE_B) or self._get_dp(DP_VOLTAGE_A)
        if raw is None:
            return None
        try:
            return float(raw)
        except Exception:
            return None

    @property
    def extra_state_attributes(self):
        return {
            "voltage_primary_dp": DP_VOLTAGE_B,
            "voltage_alt_dp": DP_VOLTAGE_A,
            "voltage_primary_raw": self._get_dp(DP_VOLTAGE_B),
            "voltage_alt_raw": self._get_dp(DP_VOLTAGE_A),
        }


class PortaCoolCategoryStatusSensor(_BasePortaCoolSensor):
    def __init__(self, coordinator, api, entry, cat_num: str, cat_name: str):
        super().__init__(coordinator, api, entry)
        self._cat_num = cat_num
        self._attr_name = f"{cat_name} Status"
        self._attr_unique_id = f"{self._api.device_id}_alert_{cat_num}"

    @property
    def native_value(self):
        alerts = self._get_alerts()
        active = [
            a for a in alerts
            if _category_key(a.get("alertId", "")) == self._cat_num and _is_active(a)
        ]
        return _severity(active)

    @property
    def extra_state_attributes(self):
        alerts = self._get_alerts()
        active = [
            a for a in alerts
            if _category_key(a.get("alertId", "")) == self._cat_num and _is_active(a)
        ]
        return {"active_count": len(active), "active_alerts": active}


class PortaCoolOverallStatusSensor(_BasePortaCoolSensor):
    _attr_name = "Overall Status"
    _attr_icon = "mdi:shield-alert-outline"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator, api, entry)
        self._attr_unique_id = f"{self._api.device_id}_overall_status"

    @property
    def native_value(self):
        alerts = self._get_alerts()
        active = [a for a in alerts if _is_active(a)]
        return _severity(active)

    @property
    def extra_state_attributes(self):
        alerts = self._get_alerts()
        active = [a for a in alerts if _is_active(a)]
        return {"active_count": len(active)}


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    api = data["api"]
    coordinator = data["coordinator"]

    entities: list[SensorEntity] = [
        PortaCoolTimerRemainingSensor(coordinator, api, entry),
        PortaCoolExitTemperatureSensor(coordinator, api, entry),
        PortaCoolAmbientTemperatureSensor(coordinator, api, entry),
        PortaCoolInputVoltageSensor(coordinator, api, entry),
        PortaCoolOverallStatusSensor(coordinator, api, entry),
    ]

    for cat_num, cat_name in ALERT_CATEGORIES.items():
        entities.append(PortaCoolCategoryStatusSensor(coordinator, api, entry, cat_num, cat_name))

    async_add_entities(entities, True)