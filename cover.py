"""Somfy UAI+ window covers"""
import logging
from typing import Any
import voluptuous as vol

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
import homeassistant.helpers.device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import DOMAIN
from .coordinator import SomfyUaiPlusCoordinator

SERVICE_SET_COVER_INTERMEDIATE_POSITION = "set_cover_intermediate_position"

_LOGGER = logging.getLogger("somfy_uai_plus")

known_models_from_types = {
    "Glydea": {
        "full_name": "Glydea",
        "device_class": CoverDeviceClass.CURTAIN,
    },
    "Sonesse 30": {
        "full_name": "Sonesse 30",
        "device_class": CoverDeviceClass.SHADE,
    },
    "LSU 50": {
        "full_name": "Sonesse 50",
        "device_class": CoverDeviceClass.SHADE,
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
) -> None:
    """Setup config entry"""
    data = hass.data[DOMAIN][config.entry_id]
    coordinator: SomfyUaiPlusCoordinator = data["coordinator"]

    platform = entity_platform.async_get_current_platform()

    # This will call Entity.set_sleep_timer(sleep_time=VALUE)
    platform.async_register_entity_service(
        SERVICE_SET_COVER_INTERMEDIATE_POSITION,
        {
            vol.Required("intermediate_position"): cv.positive_int,
        },
        "async_set_cover_intermediate_position",
    )

    uai_plus_device_unique_id: str = coordinator.device_unique_id

    covers: list(SomfyCover) = []
    groups: list(SomfyCoverGroup) = []

    target_ids = config.options.get("target_ids")
    if target_ids is None:
        target_ids = []

    group_ids = config.options.get("group_ids")
    if group_ids is None:
        group_ids = []

    for target_id in target_ids:
        cover: SomfyCover = SomfyCover(coordinator, target_id)
        covers.append(cover)

    for group_id in group_ids:
        group: SomfyCoverGroup = SomfyCoverGroup(coordinator, group_id)
        groups.append(group)

    cover_device_identifiers = list(
        map(lambda x: x.device_info.get("identifiers"), covers)
    )
    group_device_identifiers = list(
        map(lambda x: x.device_info.get("identifiers"), groups)
    )

    device_registry = dr.async_get(hass)
    device_entries = dr.async_entries_for_config_entry(device_registry, config.entry_id)
    target_and_group_device_entries = list(
        filter(
            lambda x: any(
                i[1].startswith(f"{uai_plus_device_unique_id}_target_")
                or i[1].startswith(f"{uai_plus_device_unique_id}_group_")
                for i in x.identifiers
            ),
            device_entries,
        )
    )
    for target_or_group_device_entry in target_and_group_device_entries:
        if (
            not target_or_group_device_entry.identifiers in cover_device_identifiers
            and not target_or_group_device_entry.identifiers in group_device_identifiers
        ):
            device_registry.async_remove_device(target_or_group_device_entry.id)

    add_entities(covers)
    add_entities(groups)


class SomfyCover(CoordinatorEntity, CoverEntity):
    """Somfy UAI+ cover device."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
        | CoverEntityFeature.STOP
    )

    _attr_current_cover_position: int | None = None
    _attr_device_class: CoverDeviceClass | None = None
    _attr_is_closed: bool | None = None
    _attr_is_closing: bool | None = None
    _attr_is_opening: bool | None = None

    def __init__(self, coordinator: SomfyUaiPlusCoordinator, target_id: str) -> None:
        """Initialize."""
        super().__init__(coordinator)

        uai_plus_device_unique_id: str = coordinator.device_unique_id

        self._target_id: str = target_id
        self._attr_unique_id = target_id
        self._attr_name = f"Cover {target_id}"

        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, target_id),
                (DOMAIN, f"{uai_plus_device_unique_id}_target_{target_id}"),
            },
            name=self._attr_name,
            manufacturer="Somfy",
            via_device=(DOMAIN, uai_plus_device_unique_id),
        )

        self._set_state_from_device()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        coordinator: SomfyUaiPlusCoordinator = self.coordinator
        await coordinator.async_move_target_down(self._target_id)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        coordinator: SomfyUaiPlusCoordinator = self.coordinator
        await coordinator.async_move_target_up(self._target_id)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        coordinator: SomfyUaiPlusCoordinator = self.coordinator
        await coordinator.async_stop_target(self._target_id)

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set the cover position"""
        position: int = kwargs[ATTR_POSITION]
        coordinator: SomfyUaiPlusCoordinator = self.coordinator
        await coordinator.async_move_target_to_closed_percentage(
            self._target_id, 100 - position
        )

    async def async_set_cover_intermediate_position(
        self, intermediate_position: int
    ) -> None:
        """Set the cover intermediate position."""
        coordinator: SomfyUaiPlusCoordinator = self.coordinator
        await coordinator.async_move_target_to_intermediate_position(
            self._target_id, intermediate_position
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._set_state_from_device()
        self.async_write_ha_state()

    def _set_state_from_device(self):
        coordinator: SomfyUaiPlusCoordinator = self.coordinator

        device_state: dict(str, Any) = coordinator.data["device_states"].get(
            self._target_id
        )

        self._attr_available = False

        if device_state is not None:
            device_state_type = device_state["type"]
            name = device_state["name"]

            model_name = device_state_type
            known_model = known_models_from_types.get(device_state_type)
            device_class = None
            if known_model is not None:
                model_name = known_model["full_name"]
                device_class = known_model["device_class"]

            if (
                self._attr_device_info.get("model") != model_name
                or self._attr_device_info.get("name") != name
            ):
                self._attr_device_info["model"] = model_name
                self._attr_device_info["name"] = name

                device_registry = dr.async_get(self.hass)
                device_entry = device_registry.async_get_device(
                    {(DOMAIN, self._target_id)}
                )
                device_registry.async_update_device(
                    device_entry.id, model=model_name, name=name
                )

            self._attr_name = name
            self._attr_device_class = device_class

            closed_percentage = device_state["closed_percentage"]
            position = 100 - closed_percentage
            last_position = self.current_cover_position

            self._attr_available = coordinator.is_connection_ready
            self._attr_current_cover_position = position
            self._attr_is_closed = position == 0
            self._attr_is_opening = False
            self._attr_is_closing = False
            if last_position is not None and 100 > position > 0:
                self._attr_is_opening = last_position < position
                self._attr_is_closing = last_position > position


class SomfyCoverGroup(CoordinatorEntity, CoverEntity):
    """Somfy UAI+ cover group device."""

    _attr_supported_features = (
        CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE | CoverEntityFeature.STOP
    )

    _attr_is_closed: bool | None = None

    def __init__(self, coordinator: SomfyUaiPlusCoordinator, group_id: str) -> None:
        """Initialize."""
        super().__init__(coordinator)

        uai_plus_device_unique_id: str = coordinator.device_unique_id

        self._group_id: str = group_id
        self._attr_unique_id = group_id
        self._attr_name = f"Group {group_id}"

        self._attr_device_info = DeviceInfo(
            identifiers={
                (DOMAIN, group_id),
                (DOMAIN, f"{uai_plus_device_unique_id}_group_{group_id}"),
            },
            name=self._attr_name,
            manufacturer="Somfy",
            via_device=(DOMAIN, uai_plus_device_unique_id),
        )

        self._set_state_from_device()

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the group's covers."""
        coordinator: SomfyUaiPlusCoordinator = self.coordinator
        await coordinator.async_move_target_down(self._group_id)

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the group's covers."""
        coordinator: SomfyUaiPlusCoordinator = self.coordinator
        await coordinator.async_move_target_up(self._group_id)

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the group's covers."""
        coordinator: SomfyUaiPlusCoordinator = self.coordinator
        await coordinator.async_stop_target(self._group_id)

    async def async_set_cover_intermediate_position(
        self, intermediate_position: int
    ) -> None:
        """Set the group's covers' intermediate positions."""
        coordinator: SomfyUaiPlusCoordinator = self.coordinator
        await coordinator.async_move_target_to_intermediate_position(
            self._group_id, intermediate_position
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._set_state_from_device()
        self.async_write_ha_state()

    def _set_state_from_device(self):
        coordinator: SomfyUaiPlusCoordinator = self.coordinator

        device_state: dict(str, Any) = coordinator.data["device_states"].get(
            self._group_id
        )

        self._attr_available = False

        if device_state is not None:
            name = device_state["name"]

            if self._attr_device_info.get("name") != name:
                self._attr_device_info["name"] = name

                device_registry = dr.async_get(self.hass)
                device_entry = device_registry.async_get_device(
                    {(DOMAIN, self._group_id)}
                )
                device_registry.async_update_device(device_entry.id, name=name)

            self._attr_name = name

            self._attr_available = coordinator.is_connection_ready
