"""Config flow for flashbird integration."""
from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from .apsystems_ecu import EcuClient, EcuData
from homeassistant.helpers.dispatcher import async_dispatcher_send
from .const import DOMAIN, COORDINATOR

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("address"): str,
        vol.Required("alias"): str,
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> [Any]:
    client = EcuClient(data["address"], data["alias"])
    response = await client.get_ecu_data()
    if response is None:
        raise CannotConnect
    else:
        return {"ECU": {"address": data["address"], "alias": data["alias"]}}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 1

    async def async_step_user(self, data: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if data is not None:
            try:
                data["alias"] = re.sub(r"[^0-9a-zA-Z]+", "", data["alias"])
                info = await validate_input(self.hass, data)

                return self.async_create_entry(title=info["ECU"]["alias"], data=data)
            except CannotConnect:
                errors["base"] = "cannot_connect"
                _LOGGER.exception("Cannot connect")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
