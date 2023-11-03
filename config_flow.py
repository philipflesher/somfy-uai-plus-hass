"""Config flow"""

from __future__ import annotations
from async_timeout import timeout
import logging
import re
import string
import voluptuous as vol

from homeassistant import config_entries, exceptions
from homeassistant.const import (
    CONF_HOST,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_NAME,
    CONF_UNIQUE_ID,
)
from homeassistant.core import callback, HomeAssistant
from homeassistant.data_entry_flow import FlowResult
import homeassistant.helpers.config_validation as cv

from somfy_uai_plus_telnet.telnet_client import (
    TelnetClient,
    ReaderClosedException,
    InvalidUserException,
    InvalidPasswordException,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

INIT_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)

IDENTIFIERS_DATA_SCHEMA = vol.Schema(
    {vol.Required(CONF_UNIQUE_ID): str, vol.Required(CONF_NAME): str}
)


def is_valid_hostname(hostname):
    """Validate hostname string"""
    if len(hostname) > 255:
        return False
    if hostname[-1] == ".":
        hostname = hostname[:-1]  # strip exactly one dot from the right, if present
    allowed = re.compile(r"(?!-)[A-Z\d-]{1,63}(?<!-)$", re.IGNORECASE)
    return all(allowed.match(x) for x in hostname.split("."))


async def async_validate_connection(hass: HomeAssistant, data: dict):
    """Validate the user input, allowing us to connect.
    Data has the keys from INIT_DATA_SCHEMA with values provided by the user.
    """
    # Validate the data can be used to set up a connection.
    if not is_valid_hostname(data[CONF_HOST]):
        raise InvalidHost

    async def no_op(optional=None):
        pass

    telnet_client = TelnetClient(
        host=data[CONF_HOST],
        user=data[CONF_USERNAME],
        password=data[CONF_PASSWORD],
        async_on_connection_ready=no_op,
        async_on_disconnected=no_op,
    )

    # Ensure connection succeeds and sample command works
    try:
        await telnet_client.async_connect()
        async with timeout(5):
            await telnet_client.async_wait_for_connection_establishment()
            await telnet_client.async_disconnect()
    except ConnectionError as exc:
        raise CannotConnect from exc


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Somfy UAI+."""

    VERSION = 1
    # Pick one of the available connection classes in homeassistant/config_entries.py
    # This tells HA if it should be asking for updates, or it'll be notified of updates
    # automatically.
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        self._host = None
        self._username = None
        self._password = None

    async def async_step_user(self, user_input=None):
        """Start the user config flow."""
        return await self.async_step_init()

    async def async_step_init(self, user_input=None):
        """Handle the initial step."""
        errors = {}
        if user_input is not None:
            try:
                await async_validate_connection(self.hass, user_input)
                self._host = user_input[CONF_HOST]
                self._username = user_input[CONF_USERNAME]
                self._password = user_input[CONF_PASSWORD]
                return await self.async_step_identifiers()
            except CannotConnect:
                errors[CONF_HOST] = "cannot_connect"
            except InvalidHost:
                errors[CONF_HOST] = "invalid_host"
            except ReaderClosedException as exc:
                if type(exc.cause) is InvalidUserException:
                    errors[CONF_HOST] = "invalid_username"
                if type(exc.cause) is InvalidPasswordException:
                    errors[CONF_HOST] = "invalid_password"
            except:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
                raise

        return self.async_show_form(
            step_id="init", data_schema=INIT_DATA_SCHEMA, errors=errors
        )

    async def async_step_identifiers(self, user_input=None):
        """Handle the identifiers step."""
        errors = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_UNIQUE_ID])
            self._abort_if_unique_id_configured()

            entry_data = {
                "host": self._host,
                "username": self._username,
                "password": self._password,
                "unique_id": user_input[CONF_UNIQUE_ID],
                "name": user_input[CONF_NAME],
            }

            return self.async_create_entry(title=entry_data["name"], data=entry_data)

        return self.async_show_form(
            step_id="identifiers", data_schema=IDENTIFIERS_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    @staticmethod
    def _is_6_digit_hexadecimal(s: str) -> bool:
        return len(s) == 6 and all(c in string.hexdigits for c in s)

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        existing_target_ids = self.config_entry.options.get("target_ids")
        if existing_target_ids is None:
            existing_target_ids = []

        existing_group_ids = self.config_entry.options.get("group_ids")
        if existing_group_ids is None:
            existing_group_ids = []

        errors = {}
        if user_input is not None:
            edited_target_ids = user_input.get("existing_target_ids")
            new_target_id = user_input.get("target_id")
            new_target_ids = []
            if new_target_id is not None:
                if new_target_id in existing_target_ids:
                    errors["target_id"] = "target_id_exists"
                elif not OptionsFlowHandler._is_6_digit_hexadecimal(new_target_id):
                    errors["target_id"] = "invalid_target_id"
                else:
                    new_target_ids.append(new_target_id)
            if edited_target_ids is not None:
                new_target_ids.extend(edited_target_ids)
            else:
                new_target_ids.extend(existing_target_ids)
            new_target_ids.sort()

            edited_group_ids = user_input.get("existing_group_ids")
            new_group_id = user_input.get("group_id")
            new_group_ids = []
            if new_group_id is not None:
                if new_group_id in existing_group_ids:
                    errors["group_id"] = "group_id_exists"
                elif not OptionsFlowHandler._is_6_digit_hexadecimal(new_group_id):
                    errors["group_id"] = "invalid_group_id"
                else:
                    new_group_ids.append(new_group_id)
            if edited_group_ids is not None:
                new_group_ids.extend(edited_group_ids)
            else:
                new_group_ids.extend(existing_group_ids)
            new_group_ids.sort()

            if len(errors) == 0:
                saved_options = {}
                saved_options["target_ids"] = new_target_ids
                saved_options["group_ids"] = new_group_ids
                return self.async_create_entry(title="", data=saved_options)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "existing_target_ids", default=existing_target_ids
                    ): cv.multi_select(existing_target_ids),
                    vol.Optional(
                        "existing_group_ids", default=existing_group_ids
                    ): cv.multi_select(existing_group_ids),
                    vol.Optional("target_id"): cv.string,
                    vol.Optional("group_id"): cv.string,
                }
            ),
            errors=errors,
        )


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidHost(exceptions.HomeAssistantError):
    """Error to indicate there is an invalid hostname."""
