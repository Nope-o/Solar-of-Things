"""Binary sensors for the Solar of Things integration."""
from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create binary sensors for device online status."""
    data = hass.data[DOMAIN][entry.entry_id]
    device_coordinators = data["device_coordinators"]

    entities: list[BinarySensorEntity] = []
    for device_id, coordinator in device_coordinators.items():
        device_name = (coordinator.device_meta or {}).get("name") or device_id
        entities.append(SolarOfThingsOnlineBinarySensor(coordinator, device_name))

    async_add_entities(entities)


class SolarOfThingsOnlineBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Expose inverter online/offline status as a Home Assistant binary sensor."""

    def __init__(self, coordinator, device_name: str) -> None:
        super().__init__(coordinator)
        self._device_name = device_name
        self._attr_has_entity_name = True
        self._attr_name = "Online"
        self._attr_icon = "mdi:power-plug"
        self._attr_unique_id = f"{DOMAIN}_{self.coordinator.device_id}_online"

    @property
    def is_on(self) -> bool:
        metrics = (self.coordinator.data or {}).get("device_metrics") or {}
        return bool(metrics.get("online"))

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.device_id)},
            "name": self._device_name,
            "manufacturer": "Siseli",
            "model": (self.coordinator.data.get("device_meta") or {}).get("model") if self.coordinator.data else None,
            "via_device": (DOMAIN, self.coordinator.station_id),
        }
