"""Somfy UAI+ data update coordinator"""

from __future__ import annotations
import asyncio
from datetime import timedelta
import logging
import voluptuous as vol

from homeassistant.components.cover import (
    PLATFORM_SCHEMA,
)

from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from somfy_uai_plus_telnet.telnet_client import (
    ErrorResponseException,
    GroupInfo,
    ReaderClosedException,
    TargetInfo,
    TelnetClient,
)

_LOGGER = logging.getLogger("somfy_uai_plus")

# Validation of user configuration
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME): cv.string,
        vol.Required(CONF_HOST): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }
)


class SomfyUaiPlusCoordinator(DataUpdateCoordinator):
    """Somfy UAI+ data update coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        username: str,
        password: str,
        target_ids: list(str),
        group_ids: list(str),
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Somfy UAI+",
            update_interval=timedelta(milliseconds=1000),
        )
        self._host: str = host
        self._username: str = username
        self._password: str = password
        self._target_ids: list(str) = target_ids
        self._group_ids: list(str) = group_ids
        self._telnet_client: TelnetClient = TelnetClient(
            self._host,
            self._username,
            self._password,
            async_on_connection_ready=self._async_on_connection_ready,
            async_on_disconnected=self._async_on_disconnected,
        )
        self._is_connection_ready: bool = False
        self._should_reconnect: bool = False
        self._connection_task: asyncio.Task = None

        self.device_unique_id: str = self.config_entry.unique_id
        self.device_name: str = self.config_entry.title

        data = {"device_states": {}}
        self.async_set_updated_data(data)

    @property
    def is_connection_ready(self) -> bool:
        """Gets a value indicating whether the underlying connection is established."""
        return self._is_connection_ready

    async def async_wait_for_connection_ready(self) -> None:
        """Waits for connection establishment."""
        await self._telnet_client.async_wait_for_connection_establishment()

    def connect_and_stay_connected(self) -> None:
        """Connect to the ISP; if the connection is dropped, reconnect indefinitely."""
        self._should_reconnect = True
        self._connection_task = asyncio.create_task(self._async_connect())

    async def _async_connect(self):
        while True:
            try:
                await self._telnet_client.async_connect()
                # await self._async_on_data_update()
                break
            except ConnectionError:
                if not self._should_reconnect:
                    break
                await asyncio.sleep(2)

    async def _async_on_connection_ready(self) -> None:
        self._is_connection_ready = True

    async def _async_on_disconnected(
        self, reader_closed_exception: ReaderClosedException
    ) -> None:
        self._is_connection_ready = False
        if self._should_reconnect:
            self.connect_and_stay_connected()

    async def _async_update_data(self):
        """Update the data from the UAI+"""
        device_states = {}
        if self.is_connection_ready:
            previous_device_states = self.data["device_states"]

            for target_id in self._target_ids:
                previous_device_state = previous_device_states.get(target_id)
                new_name: str = None
                new_type: str = None
                if previous_device_state is not None:
                    new_name = previous_device_state.get("name")
                    new_type = previous_device_state.get("type")
                try:
                    if new_name is None or new_type is None:
                        info: TargetInfo = (
                            await self._telnet_client.async_get_target_info(target_id)
                        )
                        new_name = info.name
                        new_type = info.type

                    closed_percentage: int = (
                        await self._telnet_client.async_get_target_position(target_id)
                    )
                    device_states[target_id] = {
                        "name": new_name,
                        "type": new_type,
                        "closed_percentage": closed_percentage,
                    }
                except ErrorResponseException as err:
                    _LOGGER.warning(
                        f"Request for target ID {target_id} failed with error: {err}."
                    )

            for group_id in self._group_ids:
                previous_device_state = previous_device_states.get(group_id)
                new_name: str = None
                if previous_device_state is not None:
                    new_name = previous_device_state.get("name")
                try:
                    if new_name is None:
                        info: GroupInfo = (
                            await self._telnet_client.async_get_group_info(group_id)
                        )
                        new_name = info.name

                    device_states[group_id] = {"name": new_name}
                except ErrorResponseException as err:
                    _LOGGER.warning(
                        f"Request for group ID {group_id} failed with error: {err}."
                    )

        return {"device_states": device_states, "error": None}

    async def async_disconnect(self) -> None:
        """Disconnect from the ISP."""
        self._should_reconnect = False
        if self._connection_task is not None:
            await self._connection_task
        await self._telnet_client.async_disconnect()

    async def async_move_target_up(self, target_id: str) -> None:
        await self._telnet_client.async_move_target_up(target_id)

    async def async_move_target_down(self, target_id: str) -> None:
        await self._telnet_client.async_move_target_down(target_id)

    async def async_stop_target(self, target_id: str) -> None:
        await self._telnet_client.async_stop_target(target_id)

    async def async_move_target_to_closed_percentage(
        self, target_id: str, closed_percentage: int
    ) -> None:
        await self._telnet_client.async_move_target_to_position(
            target_id, closed_percentage
        )

    async def async_move_target_to_intermediate_position(
        self, target_id: str, intermediate_position: int
    ) -> None:
        await self._telnet_client.async_move_target_to_intermediate_position(
            target_id, intermediate_position
        )
