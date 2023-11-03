"""Constants"""
from homeassistant.const import Platform

from typing import Final

DOMAIN: Final = "somfy_uai_plus"
PLATFORMS: Final = [Platform.BINARY_SENSOR, Platform.COVER]
