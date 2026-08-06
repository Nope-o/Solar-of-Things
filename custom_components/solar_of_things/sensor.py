"""Sensor platform for Solar of Things integration."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SENSOR_DEFINITIONS
from .metrics import extract_device_metric_values

_LOGGER = logging.getLogger(__name__)

# Map sensor key → translation_key (snake_case)
_TRANSLATION_KEYS: dict[str, str] = {
    "pvInputPower": "pv_input_power",
    "acOutputActivePower": "ac_output_active_power",
    "batteryDischargeCurrent": "battery_discharge_current",
    "batteryChargingCurrent": "battery_charging_current",
    "batteryVoltage": "battery_voltage",
    "batteryPower": "battery_power",
    "batterySOC": "battery_soc",
    "feedInPower": "feed_in_power",
    "gridPower": "grid_power",
    "loadPower": "load_power",
    "daily_grid_import": "daily_grid_import",
    "daily_grid_export": "daily_grid_export",
    "daily_grid_net": "daily_grid_net",
    "monthly_pv_generated": "monthly_pv_generated",
    "monthly_grid_import": "monthly_grid_import",
    "monthly_grid_export": "monthly_grid_export",
    "monthly_grid_net": "monthly_grid_net",
    "monthly_total_consumption": "monthly_total_consumption",
    "monthly_solar_percentage": "monthly_solar_percentage",
    "monthly_load_estimate": "monthly_load_estimate",
    "yearly_load_estimate": "yearly_load_estimate",
    "yearly_grid_import": "yearly_grid_import",
    "yearly_grid_export": "yearly_grid_export",
    "yearly_grid_net": "yearly_grid_net",
    "current_generation_power": "current_generation_power",
    "device_online": "device_online",
    "device_state": "device_state",
    "today_pv_generated": "today_pv_generated",
    "monthly_pv_generated_device": "monthly_pv_generated_device",
    "yearly_pv_generated": "yearly_pv_generated",
    "total_pv_generated": "total_pv_generated",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Solar of Things sensors."""

    data = hass.data[DOMAIN][entry.entry_id]
    station_id: str = data["station_id"]
    device_coordinators = data["device_coordinators"]
    station_coordinator = data["station_coordinator"]

    entities: list[SensorEntity] = []

    # Per-device sensors
    for device_id, coordinator in device_coordinators.items():
        device_name = (coordinator.device_meta or {}).get("name") or device_id

        for key, definition in SENSOR_DEFINITIONS.items():
            if key.startswith("monthly_") or key.startswith("yearly_"):
                continue

            entities.append(
                SolarOfThingsDeviceSensor(
                    coordinator=coordinator,
                    station_id=station_id,
                    device_id=device_id,
                    device_name=device_name,
                    sensor_key=key,
                    sensor_definition=definition,
                )
            )

    # Station-level monthly sensors
    if station_coordinator:
        for key, definition in SENSOR_DEFINITIONS.items():
            if not key.startswith(("daily_", "monthly_", "yearly_")):
                continue

            entities.append(
                SolarOfThingsStationMonthlySensor(
                    coordinator=station_coordinator,
                    station_id=station_id,
                    sensor_key=key,
                    sensor_definition=definition,
                )
            )

    async_add_entities(entities)


class SolarOfThingsDeviceSensor(CoordinatorEntity, SensorEntity):
    """Per-device telemetry sensor."""

    def __init__(
        self,
        coordinator,
        station_id: str,
        device_id: str,
        device_name: str,
        sensor_key: str,
        sensor_definition: dict,
    ) -> None:
        super().__init__(coordinator)

        self._station_id = station_id
        self._device_id = device_id
        self._device_name = device_name
        self._sensor_key = sensor_key
        self._sensor_definition = sensor_definition

        self._attr_has_entity_name = True
        self._attr_translation_key = _TRANSLATION_KEYS.get(sensor_key)
        # Fallback name if no translation key
        if not self._attr_translation_key:
            self._attr_name = f"{device_name} {sensor_definition['name']}"
        self._attr_unique_id = f"{DOMAIN}_{station_id}_{device_id}_{sensor_key}"
        self._attr_icon = sensor_definition.get("icon")

        unit = sensor_definition.get("unit")
        if unit == "W":
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_native_unit_of_measurement = UnitOfPower.WATT
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "kWh":
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif unit == "A":
            self._attr_device_class = SensorDeviceClass.CURRENT
            self._attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "V":
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif unit == "%":
            if "battery" in sensor_key.lower():
                self._attr_device_class = SensorDeviceClass.BATTERY
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._device_id)},
            "name": self._device_name,
            "manufacturer": "Siseli",
            "model": (self.coordinator.data.get("device_meta") or {}).get("model") if self.coordinator.data else None,
            "via_device": (DOMAIN, self._station_id),
        }

    @property
    def native_value(self):
        device_metrics = (self.coordinator.data or {}).get("device_metrics") or {}
        if self._sensor_key == "device_online":
            return device_metrics.get("online")
        if self._sensor_key == "device_state":
            return device_metrics.get("device_state")
        if self._sensor_key == "current_generation_power":
            val = device_metrics.get("current_generation_power_w")
            if val is not None:
                return round(float(val), 2)

        monthly = (self.coordinator.data or {}).get("monthly") or {}
        if self._sensor_key in monthly:
            val = monthly.get(self._sensor_key)
            if val is not None:
                return round(float(val), 2)

        if self._sensor_key == "today_pv_generated":
            val = device_metrics.get("today_pv_generated_kwh")
            if val is not None:
                return round(float(val), 2)
        if self._sensor_key == "batterySOC":
            # Prefer device-reported SOC if present
            val = device_metrics.get("battery_soc_percent")
            if val is not None:
                try:
                    return round(float(val), 1)
                except Exception:
                    return None
        if self._sensor_key == "monthly_pv_generated_device":
            val = device_metrics.get("monthly_pv_generated_kwh")
            if val is not None:
                return round(float(val), 2)
        if self._sensor_key == "yearly_pv_generated":
            val = device_metrics.get("yearly_pv_generated_kwh")
            if val is not None:
                return round(float(val), 2)
        if self._sensor_key == "total_pv_generated":
            val = device_metrics.get("total_pv_generated_kwh")
            if val is not None:
                return round(float(val), 2)

        if self._sensor_key == "batteryVoltage":
            # Prefer device metric voltage (V) if available, else time-series
            val = device_metrics.get("battery_voltage_v")
            if val is not None:
                try:
                    return round(float(val), 1)
                except Exception:
                    return None

        ts = (self.coordinator.data or {}).get("time_series") or {}
        val = ts.get(self._sensor_key)
        if val is None:
            if self._sensor_key == "pvInputPower":
                val = device_metrics.get("pv_input_power_w")
            elif self._sensor_key == "loadPower":
                val = device_metrics.get("load_power_w")
            elif self._sensor_key == "gridPower":
                val = device_metrics.get("grid_power_w")
            if val is None:
                return None
        try:
            # Use 1 decimal for voltage, 2 decimals otherwise
            if self._sensor_key == "batteryVoltage":
                return round(float(val), 1)
            if self._sensor_key == "batterySOC":
                return round(float(val), 1)
            return round(float(val), 2)
        except Exception:
            return None

    @property
    def available(self) -> bool:
        """Return True if the sensor has a meaningful value to show."""
        data = self.coordinator.data or {}
        device_metrics = data.get("device_metrics") or {}
        monthly = data.get("monthly") or {}
        ts = data.get("time_series") or {}

        # Device-level simple keys
        if self._sensor_key == "device_online":
            return device_metrics.get("online") is not None
        if self._sensor_key == "device_state":
            return device_metrics.get("device_state") is not None

        # Current generation power: available if device metric or time-series present
        if self._sensor_key == "current_generation_power":
            if device_metrics.get("current_generation_power_w") is not None:
                return True
            return ts.get("current_generation_power") is not None
        if self._sensor_key == "pvInputPower":
            if device_metrics.get("pv_input_power_w") is not None:
                return True
            return ts.get("pvInputPower") is not None
        if self._sensor_key == "loadPower":
            if device_metrics.get("load_power_w") is not None:
                return True
            return ts.get("loadPower") is not None
        if self._sensor_key == "gridPower":
            if device_metrics.get("grid_power_w") is not None:
                return True
            return ts.get("gridPower") is not None
        if self._sensor_key == "batteryVoltage":
            if device_metrics.get("battery_voltage_v") is not None:
                return True
            return ts.get("batteryVoltage") is not None
        if self._sensor_key == "batterySOC":
            if device_metrics.get("battery_soc_percent") is not None:
                return True
            return ts.get("batterySOC") is not None

        # Monthly/station-derived sensors
        if self._sensor_key in monthly:
            return monthly.get(self._sensor_key) is not None

        # Device-side totals
        if self._sensor_key == "today_pv_generated":
            return device_metrics.get("today_pv_generated_kwh") is not None
        if self._sensor_key == "monthly_pv_generated_device":
            return device_metrics.get("monthly_pv_generated_kwh") is not None
        if self._sensor_key == "yearly_pv_generated":
            return device_metrics.get("yearly_pv_generated_kwh") is not None
        if self._sensor_key == "total_pv_generated":
            return device_metrics.get("total_pv_generated_kwh") is not None

        # Fallback to time-series presence
        return ts.get(self._sensor_key) is not None


class SolarOfThingsStationMonthlySensor(CoordinatorEntity, SensorEntity):
    """Station-level monthly summary sensor."""

    def __init__(
        self,
        coordinator,
        station_id: str,
        sensor_key: str,
        sensor_definition: dict,
    ) -> None:
        super().__init__(coordinator)

        self._station_id = station_id
        self._sensor_key = sensor_key
        self._sensor_definition = sensor_definition

        self._attr_has_entity_name = True
        self._attr_translation_key = _TRANSLATION_KEYS.get(sensor_key)
        if not self._attr_translation_key:
            self._attr_name = f"Station {station_id} {sensor_definition['name']}"
        self._attr_unique_id = f"{DOMAIN}_{station_id}_{sensor_key}"
        self._attr_icon = sensor_definition.get("icon")

        unit = sensor_definition.get("unit")
        if unit == "kWh":
            self._attr_device_class = SensorDeviceClass.ENERGY
            self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
            self._attr_state_class = SensorStateClass.TOTAL
        elif unit == "%":
            self._attr_native_unit_of_measurement = PERCENTAGE
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._station_id)},
            "name": f"Solar Station {self._station_id}",
            "manufacturer": "Siseli",
            "model": "Station",
        }

    @property
    def native_value(self):
        monthly = (self.coordinator.data or {}).get("monthly") or {}
        val = monthly.get(self._sensor_key)
        if val is None:
            return None
        try:
            return round(float(val), 2)
        except Exception:
            return None

    @property
    def available(self) -> bool:
        """Station-level monthly sensors are available only when monthly data exists."""
        monthly = (self.coordinator.data or {}).get("monthly") or {}
        return monthly.get(self._sensor_key) is not None
