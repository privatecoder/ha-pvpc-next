"""Sensor to collect the reference daily prices of electricity ('PVPC') in Spain."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import CURRENCY_EURO, UnitOfEnergy, UnitOfPower, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .aiopvpc.const import KEY_INJECTION, KEY_MAG, KEY_OMIE, KEY_PVPC
from .aiopvpc.utils import ensure_utc_time
from .const import DOMAIN
from .coordinator import ElecPricesDataUpdateCoordinator, PVPCConfigEntry
from .helpers import make_sensor_unique_id

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1
_PRICE_UNIT = f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"
_PRICE_LEVEL_THRESHOLDS = (
    (0.2, "very cheap"),
    (0.4, "cheap"),
    (0.6, "neutral"),
    (0.8, "expensive"),
)


@dataclass(frozen=True, kw_only=True)
class PVPCAttributeSensorDescription(SensorEntityDescription):
    """Describe a PVPC attribute-backed sensor."""

    attribute_key: str | None = None
    value_fn: Callable[[ElecPricesDataUpdateCoordinator], StateType] | None = None
    update_every_minute: bool = False


def _format_time_to_better_price(
    coordinator: ElecPricesDataUpdateCoordinator,
) -> str | None:
    current_prices = coordinator.data.sensors.get(KEY_PVPC, {})
    if not current_prices:
        return None

    now_utc = ensure_utc_time(dt_util.utcnow())
    current_hour = now_utc.replace(minute=0, second=0, microsecond=0)
    current_price = current_prices.get(current_hour)
    if current_price is None:
        return None

    next_better_ts = min(
        (
            ts_hour
            for ts_hour, price in current_prices.items()
            if ts_hour > now_utc and price < current_price
        ),
        default=None,
    )
    if not next_better_ts:
        return None

    delta_seconds = int((next_better_ts - now_utc).total_seconds())
    hours, remainder = divmod(max(delta_seconds, 0), 3600)
    minutes = remainder // 60
    return f"{hours:02d}:{minutes:02d}"


def _price_ratio_category(
    coordinator: ElecPricesDataUpdateCoordinator,
) -> str | None:
    attributes = coordinator.api.sensor_attributes.get(KEY_PVPC, {})
    price_ratio = attributes.get("price_ratio")
    if price_ratio is None:
        return None
    return _price_level_from_ratio(price_ratio)


def _next_price_value(
    coordinator: ElecPricesDataUpdateCoordinator,
) -> float | None:
    current_prices = coordinator.data.sensors.get(KEY_PVPC, {})
    if not current_prices:
        return None
    now_utc = ensure_utc_time(dt_util.utcnow())
    current_hour = now_utc.replace(minute=0, second=0, microsecond=0)
    next_hour = current_hour + timedelta(hours=1)
    if next_hour in current_prices:
        return current_prices[next_hour]
    next_ts = min((ts for ts in current_prices if ts > current_hour), default=None)
    if not next_ts:
        return None
    return current_prices[next_ts]


def _next_price_level(
    coordinator: ElecPricesDataUpdateCoordinator,
) -> str | None:
    next_price = _next_price_value(coordinator)
    if next_price is None:
        return None
    current_prices = coordinator.data.sensors.get(KEY_PVPC, {})
    if not current_prices:
        return None
    min_price = min(current_prices.values())
    max_price = max(current_prices.values())
    if max_price == min_price:
        return "neutral"
    price_ratio = (next_price - min_price) / (max_price - min_price)
    return _price_level_from_ratio(price_ratio)


def _better_price_level(
    coordinator: ElecPricesDataUpdateCoordinator,
) -> str | None:
    attributes = coordinator.api.sensor_attributes.get(KEY_PVPC, {})
    next_better_price = attributes.get("next_better_price")
    if next_better_price is None:
        return None
    current_prices = coordinator.data.sensors.get(KEY_PVPC, {})
    if not current_prices:
        return None
    min_price = min(current_prices.values())
    max_price = max(current_prices.values())
    if max_price == min_price:
        return "neutral"
    price_ratio = (next_better_price - min_price) / (max_price - min_price)
    return _price_level_from_ratio(price_ratio)


def _price_level_from_ratio(price_ratio: float) -> str:
    for threshold, label in _PRICE_LEVEL_THRESHOLDS:
        if price_ratio < threshold:
            return label
    return "very expensive"


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=KEY_PVPC,
        icon="mdi:currency-eur",
        native_unit_of_measurement=_PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        name="Current Price",
    ),
    SensorEntityDescription(
        key=KEY_INJECTION,
        icon="mdi:transmission-tower-export",
        native_unit_of_measurement=_PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        name="Injection Price",
    ),
    SensorEntityDescription(
        key=KEY_MAG,
        icon="mdi:bank-transfer",
        native_unit_of_measurement=_PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        name="MAG tax",
        entity_registry_enabled_default=False,
    ),
    SensorEntityDescription(
        key=KEY_OMIE,
        icon="mdi:shopping",
        native_unit_of_measurement=_PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        name="OMIE Price",
        entity_registry_enabled_default=False,
    ),
)
# pylint: disable=unexpected-keyword-arg
ATTRIBUTE_SENSOR_TYPES: tuple[PVPCAttributeSensorDescription, ...] = (
    PVPCAttributeSensorDescription(
        key="pvpc_data_id",
        name="PVPC Data ID",
        attribute_key="data_id",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_tariff",
        name="Tariff",
        attribute_key="tariff",
        icon="mdi:map",
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_period",
        name="Current Period",
        attribute_key="period",
        icon="mdi:clock-outline",
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_available_power",
        name="Available Power",
        attribute_key="available_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_next_period",
        name="Next Period",
        attribute_key="next_period",
        icon="mdi:clock-outline",
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_hours_to_next_period",
        name="Hours To Next Period",
        attribute_key="hours_to_next_period",
        native_unit_of_measurement=UnitOfTime.HOURS,
        device_class=SensorDeviceClass.DURATION,
        icon="mdi:timer-sand",
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_min_price",
        name="Min Price",
        attribute_key="min_price",
        native_unit_of_measurement=_PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        icon="mdi:arrow-down-bold",
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_max_price",
        name="Max Price",
        attribute_key="max_price",
        native_unit_of_measurement=_PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        icon="mdi:arrow-up-bold",
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_next_better_price",
        name="Better Price",
        attribute_key="next_better_price",
        native_unit_of_measurement=_PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        icon="mdi:arrow-collapse-down",
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_next_price",
        name="Next Price",
        value_fn=_next_price_value,
        native_unit_of_measurement=_PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        icon="mdi:arrow-right-bold",
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_next_price_level",
        name="Next Price Level",
        value_fn=_next_price_level,
        update_every_minute=False,
        icon="mdi:scale-balance",
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_time_to_better_price",
        name="Better Price In",
        value_fn=_format_time_to_better_price,
        update_every_minute=True,
        icon="mdi:clock-outline",
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_num_better_prices_ahead",
        name="Num Better Prices Ahead",
        attribute_key="num_better_prices_ahead",
        icon="mdi:counter",
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_price_ratio_category",
        name="Current Price Level",
        value_fn=_price_ratio_category,
        update_every_minute=False,
        icon="mdi:scale-balance",
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_better_price_level",
        name="Better Price Level",
        value_fn=_better_price_level,
        update_every_minute=False,
        icon="mdi:scale-balance",
    ),
)
# pylint: enable=unexpected-keyword-arg
_PRICE_SENSOR_ATTRIBUTES_MAP = {
    "name": "data_name",
    "price_position": "price_position",
    "price_ratio": "price_ratio",
    "max_price_at": "max_price_at",
    "min_price_at": "min_price_at",
    "next_best_at": "next_best_at",
    "price_00h": "price_00h",
    "price_01h": "price_01h",
    "price_02h": "price_02h",
    "price_02h_d": "price_02h_d",  # only on DST day change with 25h
    "price_03h": "price_03h",
    "price_04h": "price_04h",
    "price_05h": "price_05h",
    "price_06h": "price_06h",
    "price_07h": "price_07h",
    "price_08h": "price_08h",
    "price_09h": "price_09h",
    "price_10h": "price_10h",
    "price_11h": "price_11h",
    "price_12h": "price_12h",
    "price_13h": "price_13h",
    "price_14h": "price_14h",
    "price_15h": "price_15h",
    "price_16h": "price_16h",
    "price_17h": "price_17h",
    "price_18h": "price_18h",
    "price_19h": "price_19h",
    "price_20h": "price_20h",
    "price_21h": "price_21h",
    "price_22h": "price_22h",
    "price_23h": "price_23h",
    # only seen in the evening
    "next_better_price (next day)": "next_better_price (next day)",
    "hours_to_better_price (next day)": "hours_to_better_price (next day)",
    "num_better_prices_ahead (next day)": "num_better_prices_ahead (next day)",
    "price_position (next day)": "price_position (next day)",
    "price_ratio (next day)": "price_ratio (next day)",
    "max_price (next day)": "max_price (next day)",
    "max_price_at (next day)": "max_price_at (next day)",
    "min_price (next day)": "min_price (next day)",
    "min_price_at (next day)": "min_price_at (next day)",
    "next_best_at (next day)": "next_best_at (next day)",
    "price_next_day_00h": "price_next_day_00h",
    "price_next_day_01h": "price_next_day_01h",
    "price_next_day_02h": "price_next_day_02h",
    "price_next_day_02h_d": "price_next_day_02h_d",
    "price_next_day_03h": "price_next_day_03h",
    "price_next_day_04h": "price_next_day_04h",
    "price_next_day_05h": "price_next_day_05h",
    "price_next_day_06h": "price_next_day_06h",
    "price_next_day_07h": "price_next_day_07h",
    "price_next_day_08h": "price_next_day_08h",
    "price_next_day_09h": "price_next_day_09h",
    "price_next_day_10h": "price_next_day_10h",
    "price_next_day_11h": "price_next_day_11h",
    "price_next_day_12h": "price_next_day_12h",
    "price_next_day_13h": "price_next_day_13h",
    "price_next_day_14h": "price_next_day_14h",
    "price_next_day_15h": "price_next_day_15h",
    "price_next_day_16h": "price_next_day_16h",
    "price_next_day_17h": "price_next_day_17h",
    "price_next_day_18h": "price_next_day_18h",
    "price_next_day_19h": "price_next_day_19h",
    "price_next_day_20h": "price_next_day_20h",
    "price_next_day_21h": "price_next_day_21h",
    "price_next_day_22h": "price_next_day_22h",
    "price_next_day_23h": "price_next_day_23h",
}


async def async_setup_entry(
    _hass: HomeAssistant,
    entry: PVPCConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the electricity price sensor from config_entry."""
    coordinator = entry.runtime_data
    sensors = [ElecPriceSensor(coordinator, SENSOR_TYPES[0], entry.unique_id)]
    unique_id = entry.unique_id or entry.entry_id
    sensors.extend(
        PVPCAttributeSensor(coordinator, sensor_desc, unique_id)
        for sensor_desc in ATTRIBUTE_SENSOR_TYPES
    )
    if coordinator.api.using_private_api:
        sensors.extend(
            ElecPriceSensor(coordinator, sensor_desc, entry.unique_id)
            for sensor_desc in SENSOR_TYPES[1:]
        )
    async_add_entities(sensors)


class ElecPriceSensor(CoordinatorEntity[ElecPricesDataUpdateCoordinator], SensorEntity):
    """Class to hold the prices of electricity as a sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ElecPricesDataUpdateCoordinator,
        description: SensorEntityDescription,
        unique_id: str | None,
    ) -> None:
        """Initialize ESIOS sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_attribution = coordinator.api.attribution
        self._attr_unique_id = make_sensor_unique_id(unique_id, description.key)
        self._attr_device_info = DeviceInfo(
            configuration_url="https://api.esios.ree.es",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.entry_id)},
            manufacturer="REE",
            name="ESIOS",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.availability.get(
            self.entity_description.key, False
        )

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        # Enable API downloads for this sensor
        self.coordinator.api.update_active_sensors(self.entity_description.key, True)
        self.async_on_remove(
            lambda: self.coordinator.api.update_active_sensors(
                self.entity_description.key, False
            )
        )

        # Update 'state' value in hour changes
        self.async_on_remove(
            async_track_time_change(
                self.hass, self.update_current_price, second=[0], minute=[0]
            )
        )
        _LOGGER.debug(
            "Setup of ESIOS sensor %s (%s, unique_id: %s)",
            self.entity_description.key,
            self.entity_id,
            self._attr_unique_id,
        )

    @callback
    def update_current_price(self, now: datetime) -> None:
        """Update the sensor state, by selecting the current price for this hour."""
        self.coordinator.api.process_state_and_attributes(
            self.coordinator.data, self.entity_description.key, now
        )
        self.async_write_ha_state()

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.coordinator.api.states.get(self.entity_description.key)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any]:
        """Return the state attributes."""
        sensor_attributes = self.coordinator.api.sensor_attributes.get(
            self.entity_description.key, {}
        )
        return {
            _PRICE_SENSOR_ATTRIBUTES_MAP[key]: value
            for key, value in sensor_attributes.items()
            if key in _PRICE_SENSOR_ATTRIBUTES_MAP
        }


class PVPCAttributeSensor(CoordinatorEntity[ElecPricesDataUpdateCoordinator], SensorEntity):
    """Expose PVPC attributes as standalone sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: ElecPricesDataUpdateCoordinator,
        description: PVPCAttributeSensorDescription,
        unique_id: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_attribution = coordinator.api.attribution
        self._attr_unique_id = f"{unique_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            configuration_url="https://api.esios.ree.es",
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.entry_id)},
            manufacturer="REE",
            name="ESIOS",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.coordinator.data.availability.get(KEY_PVPC, False)

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        await super().async_added_to_hass()
        if self.entity_description.update_every_minute:
            self.async_on_remove(
                async_track_time_change(
                    self.hass, self._update_on_time_change, second=[0]
                )
            )

    @callback
    def _update_on_time_change(self, _now: datetime) -> None:
        """Refresh state on time changes for time-based attributes."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(self.coordinator)
        attributes = self.coordinator.api.sensor_attributes.get(KEY_PVPC, {})
        return attributes.get(self.entity_description.attribute_key)
