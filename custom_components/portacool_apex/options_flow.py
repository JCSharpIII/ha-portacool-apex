from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from .const import DOMAIN

CONF_FIREBASE_WEB_API_KEY = "firebase_web_api_key"
CONF_POLL_INTERVAL_SECONDS = "poll_interval_seconds"
CONF_OFFLINE_REFRESH_SECONDS = "offline_refresh_seconds"


class PortaCoolApexOptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for PortaCool Apex."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        super().__init__()
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            # Save options; HA will call the entry update listener (we add that in __init__.py)
            return self.async_create_entry(title="", data=user_input)

        # Defaults (safe fallbacks if const.py doesn’t define these extras)
        poll_default = 8
        try:
            from .const import POLL_INTERVAL  # type: ignore
            poll_default = int(getattr(POLL_INTERVAL, "total_seconds", lambda: 8)())
        except Exception:
            pass

        offline_default = 60

        firebase_default = ""
        try:
            from .const import FIREBASE_WEB_API_KEY_DEFAULT  # type: ignore
            firebase_default = str(FIREBASE_WEB_API_KEY_DEFAULT)
        except Exception:
            firebase_default = ""

        current_firebase = self._entry.options.get(CONF_FIREBASE_WEB_API_KEY, firebase_default)
        current_poll = self._entry.options.get(CONF_POLL_INTERVAL_SECONDS, poll_default)
        current_offline = self._entry.options.get(CONF_OFFLINE_REFRESH_SECONDS, offline_default)

        schema = vol.Schema(
            {
                vol.Optional(CONF_FIREBASE_WEB_API_KEY, default=current_firebase): str,
                vol.Optional(CONF_POLL_INTERVAL_SECONDS, default=int(current_poll)): vol.Coerce(int),
                vol.Optional(CONF_OFFLINE_REFRESH_SECONDS, default=int(current_offline)): vol.Coerce(int),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)