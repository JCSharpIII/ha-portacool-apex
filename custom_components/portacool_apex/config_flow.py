from __future__ import annotations

import aiohttp
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers import aiohttp_client

from .const import DOMAIN
from .auth import PortaCoolApexAuth
from .api import PortaCoolApexAPI


class PortaCoolApexConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_USERNAME): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
            )

        username = user_input[CONF_USERNAME]
        password = user_input[CONF_PASSWORD]

        session = aiohttp_client.async_get_clientsession(self.hass)
        auth = PortaCoolApexAuth(session, username, password)

        # Temporary API object for discovery; dummy IDs are fine for get_devices()
        api = PortaCoolApexAPI(session, auth, unique_id="0-0", device_type_id=0)

        try:
            devices = await api.get_devices()
            if not devices:
                return self.async_abort(reason="no_devices_found")
        except aiohttp.ClientResponseError as e:
            if e.status in (401, 403):
                errors["base"] = "invalid_auth"
            else:
                errors["base"] = "cannot_connect"
        except aiohttp.ClientError:
            errors["base"] = "cannot_connect"
        except Exception:
            errors["base"] = "unknown"

        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema(
                    {
                        vol.Required(CONF_USERNAME): str,
                        vol.Required(CONF_PASSWORD): str,
                    }
                ),
                errors=errors,
            )

        d = devices[0]
        title = d.get("deviceName", "PortaCool Apex")

        return self.async_create_entry(
            title=title,
            data={
                "username": username,
                "password": password,
                "unique_id": d["uniqueId"],
                "device_type_id": d["deviceTypeId"],
                "device_name": d.get("deviceName"),
                "model": d.get("modelNumber"),
            },
        )