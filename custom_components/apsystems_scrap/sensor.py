from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import callback
from homeassistant.config_entries import ConfigEntry
import datetime
from homeassistant.const import (
    UnitOfElectricPotential,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.helpers.device_registry import DeviceInfo
from .const import DOMAIN
import re
from .apsystems_ecu import EcuData, InverterData, SolarModule
from .coordinator import EcuUpdateCoordinator


@dataclass
class EcuSensorEntityDescriptionMixin:
    """Mixin for required keys."""

    value_fn: Callable[[EcuData], int | str]
    attribute_fn: Callable[[EcuData], dict[str, str]]
    name_fn: Callable[[EcuData], str]


@dataclass
class EcuSensorEntityDescription(
    SensorEntityDescription, EcuSensorEntityDescriptionMixin
):
    """Description for Ecu sensor."""


ECU_SENSOR_LIST: tuple[EcuSensorEntityDescription, ...] = (
    EcuSensorEntityDescription(
        name="Last System Power",
        name_fn=None,
        key="power",
        translation_key="power",
        value_fn=lambda data: data._power,
        attribute_fn=lambda data: {},
        icon="mdi:lightning-bolt",
        state_class=SensorStateClass.MEASUREMENT,
        unit_of_measurement=UnitOfPower.WATT,
    ),
    EcuSensorEntityDescription(
        name="Lifetime generation",
        name_fn=None,
        key="energy_lifetime",
        translation_key="energy_lifetime",
        value_fn=lambda data: data._lifetimeGeneration,
        attribute_fn=lambda data: {},
        icon="mdi:lightning-bolt",
        unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    EcuSensorEntityDescription(
        name="Generation of Current Day",
        name_fn=None,
        key="energy_day",
        translation_key="energy_day",
        value_fn=lambda data: data._dailyEnergy,
        attribute_fn=lambda data: {},
        icon="mdi:lightning-bolt",
        unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.TOTAL_INCREASING,
        last_reset=datetime.datetime.today(),
    ),
    EcuSensorEntityDescription(
        name="Number of Inverters",
        name_fn=None,
        key="number_inverters",
        translation_key="number_inverters",
        value_fn=lambda data: data._numberOfInverters,
        attribute_fn=lambda data: {},
        icon="mdi:storage-tank-outline",
    ),
    EcuSensorEntityDescription(
        name="Number of online Inverters",
        name_fn=None,
        key="number_online_inverters",
        translation_key="number_online_inverters",
        value_fn=lambda data: data._numberOfInvertersOnline,
        attribute_fn=lambda data: {},
        icon="mdi:storage-tank",
    ),
    EcuSensorEntityDescription(
        name="Software Version",
        name_fn=None,
        key="sofware_version",
        translation_key="sofware_version",
        value_fn=lambda data: data._softwareVersion,
        attribute_fn=lambda data: {},
        icon="mdi:numeric",
    ),
)

INVERTER_SENSOR_LIST: tuple[EcuSensorEntityDescription, ...] = (
    EcuSensorEntityDescription(
        name_fn=lambda data: data._id + " Frequency",
        key="freq",
        translation_key="freq",
        value_fn=lambda data: data._freq,
        attribute_fn=lambda data: {},
        icon="mdi:sine-wave",
        unit_of_measurement=UnitOfFrequency.HERTZ,
    ),
    EcuSensorEntityDescription(
        name_fn=lambda data: data._id + " Temperature",
        key="temperature",
        translation_key="temperature",
        value_fn=lambda data: data._temperature,
        attribute_fn=lambda data: {},
        icon="mdi:temperature-celsius",
        unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    EcuSensorEntityDescription(
        name_fn=lambda data: data._id + " Reporting time",
        key="reporting_time",
        translation_key="reporting_time",
        value_fn=lambda data: data._reportingtime,
        attribute_fn=lambda data: {},
        icon="mdi:calendar",
    ),
)

SOLAR_MODULE_SENSOR_LIST: tuple[EcuSensorEntityDescription, ...] = (
    EcuSensorEntityDescription(
        name_fn=lambda data, inv: inv + "-" + data._id + " Power",
        key="power",
        translation_key="power",
        value_fn=lambda data: data._power,
        attribute_fn=lambda data: {},
        icon="mdi:lightning-bolt",
        state_class=SensorStateClass.MEASUREMENT,
        unit_of_measurement=UnitOfPower.WATT,
    ),
    EcuSensorEntityDescription(
        name_fn=lambda data, inv: inv + "-" + data._id + " DC voltage",
        key="dcvoltage",
        translation_key="dcvoltage",
        value_fn=lambda data: data._dcvoltage,
        attribute_fn=lambda data: {},
        icon="mdi:current-dc",
        unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    EcuSensorEntityDescription(
        name_fn=lambda data, inv: inv + "-" + data._id + " AC voltage",
        key="acvoltage",
        translation_key="acvoltage",
        value_fn=lambda data: data._gridvoltage,
        attribute_fn=lambda data: {},
        icon="mdi:current-ac",
        unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    ecu: EcuData = coordinator.data
    list_sensor = []
    for sensor in ECU_SENSOR_LIST:
        list_sensor.append(EcuSensor(sensor, coordinator))

    for inverter in ecu._inverters:
        for sensor_inverter in INVERTER_SENSOR_LIST:
            list_sensor.append(InverterSensor(sensor_inverter, inverter, coordinator))

        for module in inverter._solarmodules:
            for sensor_solar_module in SOLAR_MODULE_SENSOR_LIST:
                list_sensor.append(
                    SolarModuleSensor(
                        sensor_solar_module,
                        module,
                        inverter._id,
                        coordinator,
                    )
                )

    async_add_entities(list_sensor)


class EcuSensor(CoordinatorEntity[EcuUpdateCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        description: EcuSensorEntityDescription,
        coordinator: EcuUpdateCoordinator,
    ) -> None:
        super().__init__(coordinator)

        ecu: EcuData = coordinator.data
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, ecu._id)}, name=ecu._alias
        )

        self._attr_unique_id = f"ecu_{ecu._alias}_{description.key}"
        self.entity_id = "sensor." + self._attr_unique_id

        self.entity_description = description
        self._attr_icon = description.icon
        self._attr_native_value = self.entity_description.value_fn(ecu)
        self._attr_native_unit_of_measurement = (
            self.entity_description.unit_of_measurement
        )

        if not description.last_reset is None:
            self._attr_last_reset = description.last_reset

    # @property
    # def native_value(self) -> int | str:
    #    """Return the value of the sensor."""
    #    return self.entity_description.value_fn(self._data)

    # @property
    # def extra_state_attributes(self) -> dict[str, str]:
    #    """Return state attributes for the sensor."""
    #    return self.entity_description.attribute_fn(self._data)

    # @property
    # def native_unit_of_measurement(self) -> str | None:
    #    """Return the unit of measurement."""
    #    return self.entity_description.unit_of_measurement

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_native_value = self.entity_description.value_fn(
            self.coordinator.data
        )
        self.async_write_ha_state()


class InverterSensor(CoordinatorEntity[EcuUpdateCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        description: EcuSensorEntityDescription,
        inverter: InverterData,
        coordinator: EcuUpdateCoordinator,
    ) -> None:
        super().__init__(coordinator)

        ecu: EcuData = coordinator.data

        self._id = inverter._id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, ecu._id)}, name=ecu._alias
        )

        self._attr_unique_id = f"inverter_{ecu._alias}_{self._id}_{description.key}"
        self.entity_id = "sensor." + self._attr_unique_id
        self.entity_description = description
        self._attr_icon = description.icon
        self._attr_name = self.entity_description.name_fn(inverter)
        self._attr_native_value = self.entity_description.value_fn(inverter)
        self._attr_native_unit_of_measurement = (
            self.entity_description.unit_of_measurement
        )

    # @property
    # def native_value(self) -> int | str:
    #    """Return the value of the sensor."""
    #    return self.entity_description.value_fn(self._data)

    # @property
    # def extra_state_attributes(self) -> dict[str, str]:
    #    """Return state attributes for the sensor."""
    #    return self.entity_description.attribute_fn(self._data)

    # @property
    # def native_unit_of_measurement(self) -> str | None:
    #    """Return the unit of measurement."""
    #    return self.entity_description.unit_of_measurement

    @callback
    def _handle_coordinator_update(self) -> None:
        ecu: EcuData = self.coordinator.data
        self._attr_native_value = self.entity_description.value_fn(
            ecu.get_inverter_by_id(self._id)
        )
        self.async_write_ha_state()


class SolarModuleSensor(CoordinatorEntity[EcuUpdateCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self,
        description: EcuSensorEntityDescription,
        module: SolarModule,
        inverter_id: str,
        coordinator: EcuUpdateCoordinator,
    ) -> None:
        super().__init__(coordinator)

        ecu: EcuData = coordinator.data

        self._inv_id = inverter_id
        self._id = re.sub(r"[^0-9a-zA-Z]+", "", module._id)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, ecu._id)}, name=ecu._alias
        )

        self._attr_unique_id = (
            f"module_{ecu._alias}_{self._inv_id}_{self._id}_{description.key}"
        )
        self.entity_id = "sensor." + self._attr_unique_id
        self.entity_description = description
        self._attr_icon = description.icon
        self._attr_name = self.entity_description.name_fn(module, inverter_id)
        self._attr_native_value = self.entity_description.value_fn(module)
        self._attr_native_unit_of_measurement = (
            self.entity_description.unit_of_measurement
        )

    # @property
    # def native_value(self) -> int | str:
    #    """Return the value of the sensor."""
    #    return self.entity_description.value_fn(self._data)

    # @property
    # def extra_state_attributes(self) -> dict[str, str]:
    #    """Return state attributes for the sensor."""
    #    return self.entity_description.attribute_fn(self._data)

    # @property
    # def native_unit_of_measurement(self) -> str | None:
    #    """Return the unit of measurement."""
    #    return self.entity_description.unit_of_measurement

    @callback
    def _handle_coordinator_update(self) -> None:
        ecu: EcuData = self.coordinator.data
        self._attr_native_value = self.entity_description.value_fn(
            ecu.get_inverter_by_id(self._inv_id).get_solarmodule_by_id(self._id)
        )
        self.async_write_ha_state()
