"""Constants for PortaCool Apex."""

from datetime import timedelta

DOMAIN = "portacool_apex"
API_BASE = "https://api.services.portacool.com"

POLL_INTERVAL = timedelta(seconds=8)

SIGNIN_ENDPOINT = "/user-api/users/signin"  # required by auth.py
INVOKE_ACTION_ENDPOINT = "/device-api/devices/invoke-action"
ALERTS_LATEST_ENDPOINT = "/device-api/devices/alerts/latest"
FIREBASE_CUSTOM_TOKEN_ENDPOINT = "/user-api/users/firebase-custom-token"

# Datapoints
DP_POWER = 12
DP_FAN_SPEED = 13
DP_PUMP_SPEED = 14
DP_TIMER = 21
DP_PUMP_MODE = 26
DP_PUMP_ENABLE = 27

# Values
POWER_VALUES = {True: "3", False: "2"}

PUMP_ENABLE_VALUES = {
    True: "2",   # Pump ON
    False: "1",  # Pump OFF
}

PUMP_MODE_VALUES = {
    "Eco": "1",
    "Max": "2",
}

# User-friendly fan labels -> API values
FAN_MODE_LABEL_TO_VALUE = {
    "Off": "0",
    "20%": "1",
    "40%": "2",
    "60%": "3",
    "80%": "4",
    "100%": "5",
}
FAN_MODE_OPTIONS = list(FAN_MODE_LABEL_TO_VALUE.keys())
FAN_VALUE_TO_LABEL = {v: k for k, v in FAN_MODE_LABEL_TO_VALUE.items()}

# Pump mode unified options
PUMP_MODE_OPTIONS = ["Off", "Eco", "1", "2", "3", "4", "5", "Max"]

TIMER_OPTIONS = {
    "Off": "1",
    "30 minutes": "2",
    "1 hour": "3",
    "2 hours": "4",
    "4 hours": "5",
    "8 hours": "6",
}

ALERT_CATEGORIES = {
    "1": "Fan",
    "2": "Pump",
    "3": "Louvers",
    "4": "Water",
    "5": "Temperature",
    "6": "Voltage",
}