from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ALERT_CATEGORIES,
    DOMAIN,
    # telemetry dps
    DP_AMBIENT_TEMP,
    DP_EXIT_TEMP,
    DP_INTERNAL_COMPONENT_TEMP,
    DP_RELATIVE_HUMIDITY,
    DP_VOLTAGE_A,
    DP_VOLTAGE_B,
    DP_FAN_FEEDBACK,
    DP_FAN_SPEED,
    # water
    DP_WATER_LEVEL,
    WATER_LEVEL_MAP,
    WATER_VALUE_EMPTY,
    WATER_VALUE_LOW,
    WATER_VALUE_OVERFLOW,
    WATER_ALERT_EMPTY,
    WATER_ALERT_LOW,
    WATER_ALERT_OVERFLOW,
    # airflow
    FAN_CFM_MAX,
)


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
    """Parse TimerExpiry like: 2026-01-29T06:54:30.3051500Z"""
    if not isinstance(ts, str) or not ts:
        return None

    s = ts.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

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


class PortaCoolAirflowSensor(_BasePortaCoolSensor):
    """DP7 = observed airflow/feedback value.

    When fan is commanded Off (DP13 == "0"), DP7 can linger briefly.
    We clamp to 0 after a grace period if fan is Off.
    """

    _attr_name = "Calculated Airflow (CFM)"
    _attr_icon = "mdi:calculator"
    _attr_state_class = "measurement"

    _OFF_GRACE_SECONDS = 10

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator, api, entry)
        # IMPORTANT: keep stable unique_id
        self._attr_unique_id = f"{self._api.device_id}_fan_feedback"

        self._last_raw: int | None = None
        self._last_change_ts: float | None = None
        self._unsub_tick = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._update_tracking()
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))
        self._unsub_tick = async_track_time_interval(self.hass, self._tick, timedelta(seconds=1))
        self.async_on_remove(self._unsub_tick)

    def _handle_coordinator_update(self) -> None:
        self._update_tracking()
        self.async_write_ha_state()

    async def _tick(self, _now: datetime) -> None:
        self.async_write_ha_state()

    def _update_tracking(self) -> None:
        raw = self._get_dp(DP_FAN_FEEDBACK)
        if raw is None:
            return
        try:
            val = int(float(raw))
        except Exception:
            return

        now = datetime.now(timezone.utc).timestamp()
        if self._last_raw is None or val != self._last_raw:
            self._last_raw = val
            self._last_change_ts = now

    def _should_clamp_off(self) -> bool:
        fan_mode = self._get_dp(DP_FAN_SPEED)
        if fan_mode != "0":
            return False

        if self._last_raw is None:
            return True
        if self._last_raw == 0:
            return True
        if self._last_change_ts is None:
            return False

        now = datetime.now(timezone.utc).timestamp()
        return (now - self._last_change_ts) >= self._OFF_GRACE_SECONDS

    @property
    def native_value(self):
        raw = self._get_dp(DP_FAN_FEEDBACK)
        if raw is None:
            return None
        try:
            val = int(float(raw))
        except Exception:
            return None

        self._update_tracking()

        if self._should_clamp_off():
            return 0

        return val

    @property
    def extra_state_attributes(self):
        return {
            "raw": self._get_dp(DP_FAN_FEEDBACK),
            "dp": DP_FAN_FEEDBACK,
            "fan_mode_dp": DP_FAN_SPEED,
            "fan_mode_raw": self._get_dp(DP_FAN_SPEED),
        }


class PortaCoolAirflowPercentSensor(_BasePortaCoolSensor):
    _attr_name = "Max Airflow %"
    _attr_icon = "mdi:percent"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = "measurement"

    def __init__(self, coordinator, api, entry, airflow_sensor: PortaCoolAirflowSensor):
        super().__init__(coordinator, api, entry)
        # IMPORTANT: keep stable unique_id
        self._attr_unique_id = f"{self._api.device_id}_fan_feedback_percent"
        self._airflow_sensor = airflow_sensor
        self._unsub_tick = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._unsub_tick = async_track_time_interval(self.hass, self._tick, timedelta(seconds=1))
        self.async_on_remove(self._unsub_tick)

    async def _tick(self, _now: datetime) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self):
        raw_val = self._airflow_sensor.native_value
        if raw_val is None:
            return None
        try:
            val = float(raw_val)
        except Exception:
            return None

        if val <= 0:
            return 0
        if FAN_CFM_MAX <= 0:
            return None

        pct = round((val / float(FAN_CFM_MAX)) * 100)
        return max(0, min(100, pct))

    @property
    def extra_state_attributes(self):
        return {
            "cfm_max": FAN_CFM_MAX,
            "dp": DP_FAN_FEEDBACK,
            "raw": self._get_dp(DP_FAN_FEEDBACK),
        }


class PortaCoolTimerRemainingSensor(_BasePortaCoolSensor):
    _attr_name = "Timer Remaining"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_icon = "mdi:timer-sand"
    _attr_state_class = "measurement"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator, api, entry)
        self._attr_unique_id = f"{self._api.device_id}_timer_remaining"

        self._expiry_raw: str | None = None
        self._expiry_dt: datetime | None = None
        self._unsub_tick = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        self._refresh_timer_info()
        self.async_on_remove(self.coordinator.async_add_listener(self._handle_coordinator_update))

        self._unsub_tick = async_track_time_interval(self.hass, self._tick, timedelta(seconds=1))
        self.async_on_remove(self._unsub_tick)

    def _handle_coordinator_update(self) -> None:
        self._refresh_timer_info()
        self.async_write_ha_state()

    async def _tick(self, _now: datetime) -> None:
        self.async_write_ha_state()

    def _refresh_timer_info(self) -> None:
        ti = self._timer_info()
        raw = ti.get("TimerExpiry")
        if raw != self._expiry_raw:
            self._expiry_raw = raw
            self._expiry_dt = _parse_timerexpiry(raw)

    @property
    def native_value(self) -> int:
        if not self._expiry_dt:
            return 0
        now = datetime.now(timezone.utc)
        remaining = int((self._expiry_dt - now).total_seconds())
        return max(0, remaining)

    @property
    def extra_state_attributes(self):
        return {
            "TimerExpiry": self._expiry_raw,
            "TimerExpiryUtc": self._expiry_dt.isoformat() if self._expiry_dt else None,
        }


class PortaCoolTemperatureSensor(_BasePortaCoolSensor):
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_device_class = "temperature"
    _attr_state_class = "measurement"

    def __init__(self, coordinator, api, entry, name: str, unique_suffix: str, dp_id: int, icon: str):
        super().__init__(coordinator, api, entry)
        self._attr_name = name
        self._attr_unique_id = f"{self._api.device_id}_{unique_suffix}"
        self._dp_id = dp_id
        self._attr_icon = icon

    @property
    def native_value(self):
        raw = self._get_dp(self._dp_id)
        if raw is None:
            return None
        try:
            return int(round(float(raw)))
        except Exception:
            return None

    @property
    def extra_state_attributes(self):
        return {"raw": self._get_dp(self._dp_id), "dp": self._dp_id}


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


class PortaCoolWaterAlertSensor(_BasePortaCoolSensor):
    """Water Alert: Tank Empty / Tank Low / Tank Overfill / OK (based on alerts)."""

    _attr_name = "Water Alert"
    _attr_icon = "mdi:water-alert"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator, api, entry)
        self._attr_unique_id = f"{self._api.device_id}_water_alert"

    @property
    def native_value(self):
        alerts = self._get_alerts()
        active = [a for a in alerts if _is_active(a)]
        active_ids = {a.get("alertId") for a in active}

        if WATER_ALERT_OVERFLOW in active_ids:
            return "Tank Overfill"
        if WATER_ALERT_EMPTY in active_ids:
            return "Tank Empty"
        if WATER_ALERT_LOW in active_ids:
            return "Tank Low"
        return "OK"

    @property
    def extra_state_attributes(self):
        alerts = self._get_alerts()
        active = [a for a in alerts if _is_active(a)]
        water_active = [a for a in active if _category_key(a.get("alertId", "")) == "4"]
        return {"active_count": len(water_active), "active_alerts": water_active}


class PortaCoolWaterLevelSensor(_BasePortaCoolSensor):
    """Water Level: numeric percent-like value for charts/gauges.

    Priority:
      1) Overfill alert => WATER_VALUE_OVERFLOW
      2) Empty alert    => WATER_VALUE_EMPTY
      3) Low alert      => WATER_VALUE_LOW
      4) DP5 bar count  => WATER_LEVEL_MAP lookup (1..5)
    """

    _attr_name = "Water Level"
    _attr_icon = "mdi:water-percent"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = "measurement"

    def __init__(self, coordinator, api, entry):
        super().__init__(coordinator, api, entry)
        self._attr_unique_id = f"{self._api.device_id}_water_level"

    @property
    def native_value(self):
        alerts = self._get_alerts()
        active = [a for a in alerts if _is_active(a)]
        active_ids = {a.get("alertId") for a in active}

        if WATER_ALERT_OVERFLOW in active_ids:
            return WATER_VALUE_OVERFLOW
        if WATER_ALERT_EMPTY in active_ids:
            return WATER_VALUE_EMPTY
        if WATER_ALERT_LOW in active_ids:
            return WATER_VALUE_LOW

        raw = self._get_dp(DP_WATER_LEVEL)
        if raw is None:
            return None
        mapped = WATER_LEVEL_MAP.get(str(raw))
        if mapped is None:
            return None
        try:
            return float(mapped)
        except Exception:
            return None

    @property
    def extra_state_attributes(self):
        return {
            "water_level_dp": DP_WATER_LEVEL,
            "water_level_raw": self._get_dp(DP_WATER_LEVEL),
            "map": WATER_LEVEL_MAP,
            "empty": WATER_VALUE_EMPTY,
            "low": WATER_VALUE_LOW,
            "overflow": WATER_VALUE_OVERFLOW,
        }


class PortaCoolCategoryStatusSensor(_BasePortaCoolSensor):
    """Status sensors for non-water categories (Fan/Pump/Louvers/Temp/Voltage)."""

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

class PortaCoolRelativeHumiditySensor(_BasePortaCoolSensor):
    """Relative Humidity (DP_RELATIVE_HUMIDITY) as %."""

    _attr_device_class = "humidity"
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = "measurement"
    _attr_icon = "mdi:water-percent"

    def __init__(
        self,
        coordinator,
        api,
        entry,
        name: str = "Relative Humidity",
        unique_suffix: str = "relative_humidity",
        dp_id: int = DP_RELATIVE_HUMIDITY,
        icon: str | None = None,
    ):
        super().__init__(coordinator, api, entry)
        self._attr_name = name
        self._attr_unique_id = f"{self._api.device_id}_{unique_suffix}"
        self._dp_id = dp_id
        if icon:
            self._attr_icon = icon

    @property
    def native_value(self) -> float | None:
        raw = self._get_dp(self._dp_id)
        if raw is None:
            return None
        try:
            val = float(raw)
        except Exception:
            return None

        # Clamp to valid RH range
        if val < 0:
            val = 0.0
        elif val > 100:
            val = 100.0

        # Keep one decimal if present; HA can chart floats fine
        return round(val, 1)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"raw": self._get_dp(self._dp_id), "dp": self._dp_id}


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

    device_name = (entry.data.get("device_name") or "").upper()
    has_louvers = any(x in device_name for x in ("APEX 500", "APEX 700"))

    airflow_raw = PortaCoolAirflowSensor(coordinator, api, entry)
    airflow_pct = PortaCoolAirflowPercentSensor(coordinator, api, entry, airflow_raw)

    temp_ambient = PortaCoolTemperatureSensor(
        coordinator, api, entry,
        name="Ambient Temperature",
        unique_suffix="ambient_temp",
        dp_id=DP_AMBIENT_TEMP,
        icon="mdi:weather-windy",
    )
    temp_exit = PortaCoolTemperatureSensor(
        coordinator, api, entry,
        name="Exit Temperature",
        unique_suffix="exit_temp",
        dp_id=DP_EXIT_TEMP,
        icon="mdi:air-conditioner",
    )
    temp_internal_component = PortaCoolTemperatureSensor(
        coordinator, api, entry,
        name="Internal Component Temperature",
        unique_suffix="internal_component_temp",
        dp_id=DP_INTERNAL_COMPONENT_TEMP,
        icon="mdi:thermometer",
    )
    relative_humidity = PortaCoolRelativeHumiditySensor(
        coordinator, api, entry,
        name="Relative Humidity",
        unique_suffix="relative_humidity",
        dp_id=DP_RELATIVE_HUMIDITY,
        icon="mdi:water-percent",
    )

    entities: list[SensorEntity] = [
        airflow_raw,
        airflow_pct,
        PortaCoolTimerRemainingSensor(coordinator, api, entry),
        temp_ambient,
        temp_exit,
        temp_internal_component,
        relative_humidity,
        PortaCoolInputVoltageSensor(coordinator, api, entry),
        PortaCoolWaterAlertSensor(coordinator, api, entry),
        PortaCoolWaterLevelSensor(coordinator, api, entry),
        PortaCoolOverallStatusSensor(coordinator, api, entry),
    ]

    # Category status sensors:
    # - Always include everything except Water (we have dedicated Water sensors)
    # - Skip Louvers on non-louver models
    for cat_num, cat_name in ALERT_CATEGORIES.items():
        if cat_num == "4":
            continue
        if cat_num == "3" and not has_louvers:
            continue
        entities.append(PortaCoolCategoryStatusSensor(coordinator, api, entry, cat_num, cat_name))

    async_add_entities(entities, True)