"""Constants for PortaCool Apex."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "portacool_apex"
API_BASE = "https://api.services.portacool.com"

# Firebase RTDB base
FIREBASE_DB = "https://portacool-prod-default-rtdb.firebaseio.com"

# Firebase public web API key (used only to exchange custom token → ID token)
# This is NOT a secret; it is safe to be static.
FIREBASE_WEB_API_KEY_DEFAULT = "AIzaSyDiIbYOmLHbfeBf5mcbGICgasL-BkzS39c"

# Options keys (used by options_flow.py / __init__.py)
CONF_FIREBASE_WEB_API_KEY = "firebase_web_api_key"
OPTIONS_POLL_INTERVAL_SECONDS = "poll_interval_seconds"
OPTIONS_OFFLINE_REFRESH_SECONDS = "offline_refresh_seconds"

# Defaults for options
DEFAULT_POLL_INTERVAL_SECONDS = 8
DEFAULT_OFFLINE_REFRESH_SECONDS = 60

# Default coordinator poll interval (used if options not set)
POLL_INTERVAL = timedelta(seconds=DEFAULT_POLL_INTERVAL_SECONDS)

# REST endpoints
SIGNIN_ENDPOINT = "/user-api/users/signin"
DEVICES_MY_ENDPOINT = "/device-api/devices/my"
INVOKE_ACTION_ENDPOINT = "/device-api/devices/invoke-action"
ALERTS_LATEST_ENDPOINT = "/device-api/devices/alerts/latest"
FIREBASE_CUSTOM_TOKEN_ENDPOINT = "/user-api/users/firebase-custom-token"

# Datapoints (command/control)
DP_POWER = 12
DP_FAN_SPEED = 13
DP_PUMP_SPEED = 14
DP_TIMER = 21
DP_PUMP_MODE = 26
DP_PUMP_ENABLE = 27

# Datapoints (telemetry)
DP_FAN_FEEDBACK = 7  # observed to correlate strongly with airflow when running
FAN_CFM_MAX = 4000  # Apex 1200 rated ~4000 CFM (adjust per model later if desired)

# Temperature datapoints (confirmed)
DP_AMBIENT_TEMP = 3  # Ambient / Intake
DP_EXIT_TEMP = 4  # Exit
DP_MEDIA_TEMP = 23  # Media/Pad
DP_WATER_TEMP = 24  # Water

# Voltage datapoints
DP_VOLTAGE_A = 31
DP_VOLTAGE_B = 32

# Water alerts (confirmed)
WATER_ALERT_LOW = "4-2"
WATER_ALERT_EMPTY = "4-3"
WATER_ALERT_OVERFLOW = "4-4"

# Water level bars (CONFIRMED): DP5 = 1..5 green bars
DP_WATER_LEVEL = 5

# Water level map (DP5 -> %)
# NOTE: Sensor logic should apply overrides for Empty/Low/Overflow using the alert IDs above.
WATER_LEVEL_MAP = {
    "1": 33.3,
    "2": 50.0,
    "3": 66.7,
    "4": 83.3,
    "5": 100.0,
}
WATER_VALUE_EMPTY = 0.0
WATER_VALUE_LOW = 16.7
WATER_VALUE_OVERFLOW = 110.0

# Power command values
POWER_VALUES = {True: "3", False: "2"}

# Pump enable values
PUMP_ENABLE_VALUES = {
    True: "2",  # Pump ON
    False: "1",  # Pump OFF
}

# Pump mode values
PUMP_MODE_VALUES = {
    "Eco": "1",
    "Max": "2",
    "Manual": "3",
}

# Fan mode labels -> API values (your updated labels)
FAN_MODE_LABEL_TO_VALUE = {
    "Off": "0",
    "10%": "1",
    "20%": "2",
    "40%": "3",
    "70%": "4",
    "100%": "5",
}
FAN_MODE_OPTIONS = list(FAN_MODE_LABEL_TO_VALUE.keys())
FAN_VALUE_TO_LABEL = {v: k for k, v in FAN_MODE_LABEL_TO_VALUE.items()}

# Pump unified selector options (if you’re using it in select.py)
PUMP_MODE_OPTIONS = ["Off", "Eco", "1", "2", "3", "4", "5", "Max"]

# Timer options
TIMER_OPTIONS = {
    "Off": "1",
    "30 minutes": "2",
    "1 hour": "3",
    "2 hours": "4",
    "4 hours": "5",
    "8 hours": "6",
}

# Alert categories (prefix before the dash)
ALERT_CATEGORIES = {
    "1": "Fan",
    "2": "Pump",
    "3": "Louvers",
    "4": "Water",
    "5": "Temperature",
    "6": "Voltage",
}