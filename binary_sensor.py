"""Somfy UAI+ binary sensors"""
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.core import callback, HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import DOMAIN
from .coordinator import SomfyUaiPlusCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
) -> None:
    """Setup config entry"""
    coordinator: SomfyUaiPlusCoordinator = hass.data[DOMAIN][config.entry_id][
        "coordinator"
    ]
    entities = [SomfyUaiPlusConnectionSensor(coordinator)]

    add_entities(entities)


class SomfyUaiPlusConnectionSensor(CoordinatorEntity, BinarySensorEntity):
    """Somfy UAI+ connection state sensor."""

    def __init__(self, coordinator: SomfyUaiPlusCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)

        device_unique_id = coordinator.device_unique_id
        device_name = coordinator.device_name
        unique_id = f"{device_unique_id}_connection_state"

        self._attr_unique_id = unique_id
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_name = f"{device_name} Connection State"

        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, device_unique_id)})

        self._set_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._set_state()
        self.async_write_ha_state()

    def _set_state(self) -> None:
        """Set state from coordinator"""
        coordinator: SomfyUaiPlusCoordinator = self.coordinator
        self._attr_is_on = coordinator.is_connection_ready
