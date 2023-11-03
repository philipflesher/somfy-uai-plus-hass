"""Somfy UAI+ Integration"""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.reload import async_setup_reload_service

from .coordinator import SomfyUaiPlusCoordinator

from .const import DOMAIN, PLATFORMS


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Setup config entry"""
    await async_setup_reload_service(hass, DOMAIN, PLATFORMS)

    host: str = entry.data["host"]
    username: str = entry.data["username"]
    password: str = entry.data["password"]

    target_ids = entry.options.get("target_ids")
    if target_ids == None:
        target_ids = []

    group_ids = entry.options.get("group_ids")
    if group_ids == None:
        group_ids = []

    coordinator = SomfyUaiPlusCoordinator(hass, host, username, password, target_ids, group_ids)
    coordinator.connect_and_stay_connected()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "host": host,
        "username": username,
        "password": password,
        "coordinator": coordinator,
    }

    device_registry = dr.async_get(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.unique_id)},
        manufacturer="Somfy",
        model="UAI+",
        name=entry.title,
    )

    entry.async_on_unload(entry.add_update_listener(update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry"""
    coordinator: SomfyUaiPlusCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]
    await coordinator.async_disconnect()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
