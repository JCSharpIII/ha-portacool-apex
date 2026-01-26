"""Constants for PortaCool Apex."""

DOMAIN = "portacool_apex"
API_BASE = "https://api.services.portacool.com"

# Proven via Postman
SIGNIN_ENDPOINT = "/user-api/users/signin"
DEVICES_MY_ENDPOINT = "/device-api/devices/my"
INVOKE_ACTION_ENDPOINT = "/device-api/devices/invoke-action"

# Datapoints (proven)
DP_POWER = 12
DP_FAN_SPEED = 13
DP_TIMER = 21

POWER_VALUES = {True: "3", False: "2"}

FAN_SPEED_MAP = {
    0: "0",
    20: "1",
    40: "2",
    60: "3",
    80: "4",
    100: "5",
}

TIMER_OPTIONS = {
    "Off": "1",
    "30 minutes": "2",
    "1 hour": "3",
    "2 hours": "4",
    "4 hours": "5",
    "8 hours": "6",
}