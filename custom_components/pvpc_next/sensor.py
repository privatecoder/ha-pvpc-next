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
from homeassistant.const import (
    CURRENCY_EURO,
    CONF_API_TOKEN,
    STATE_UNAVAILABLE,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .aiopvpc.const import (
    KEY_INJECTION,
    KEY_MAG,
    KEY_OMIE,
    KEY_PVPC,
    SENSOR_KEY_TO_DATAID,
    TARIFFS,
)
from .aiopvpc.pvpc_tariff import get_current_and_next_price_periods
from .aiopvpc.utils import ensure_utc_time
from .const import (
    ATTR_ENABLE_PRIVATE_API,
    DEFAULT_ENABLE_PRIVATE_API,
    LEGACY_ATTR_ENABLE_INJECTION_PRICE,
    DOMAIN,
    normalize_better_price_target,
)
from .coordinator import ElecPricesDataUpdateCoordinator, PVPCConfigEntry
from .helpers import make_sensor_unique_id

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 1
_PRICE_UNIT = f"{CURRENCY_EURO}/{UnitOfEnergy.KILO_WATT_HOUR}"
_PRICE_LEVEL_THRESHOLDS = (
    (0.2, "very_cheap"),
    (0.4, "cheap"),
    (0.6, "neutral"),
    (0.8, "expensive"),
)
_PRICE_LEVEL_TARGET_MAX = {
    "very_cheap": 0.2,
    "cheap": 0.4,
    "neutral": 0.6,
}
_DEBUG_LAST_UPDATE: dict[str, datetime] = {}


@dataclass(frozen=True, kw_only=True)
class PVPCAttributeSensorDescription(SensorEntityDescription):
    """Describe a PVPC attribute-backed sensor."""

    attribute_key: str | None = None
    value_fn: Callable[[ElecPricesDataUpdateCoordinator], StateType] | None = None
    update_every_minute: bool = False
    update_on_hour: bool = False


def _format_time_to_better_price(
    coordinator: ElecPricesDataUpdateCoordinator,
) -> str | None:
    current_prices = coordinator.data.sensors.get(KEY_PVPC, {})
    if not current_prices:
        return None
    next_target = _next_target_price(coordinator)
    if not next_target:
        return None
    next_ts, _price, _ratio = next_target
    now_utc = ensure_utc_time(dt_util.utcnow())
    delta_seconds = int((next_ts - now_utc).total_seconds())
    hours, remainder = divmod(max(delta_seconds, 0), 3600)
    minutes = remainder // 60
    return f"{hours:02d}:{minutes:02d}"


def _format_time_to_next_price(
    coordinator: ElecPricesDataUpdateCoordinator,
) -> str | None:
    current_prices = coordinator.data.sensors.get(KEY_PVPC, {})
    if not current_prices:
        return None
    next_price = _next_price_candidate(coordinator)
    if not next_price:
        return None
    next_ts, _price = next_price
    now_utc = ensure_utc_time(dt_util.utcnow())
    delta_seconds = int((next_ts - now_utc).total_seconds())
    hours, remainder = divmod(max(delta_seconds, 0), 3600)
    minutes = remainder // 60
    return f"{hours:02d}:{minutes:02d}"


def _format_time_to_next_period(
    coordinator: ElecPricesDataUpdateCoordinator,
) -> str | None:
    current_prices = coordinator.data.sensors.get(KEY_PVPC, {})
    if not current_prices:
        return STATE_UNAVAILABLE
    local_tz = _local_timezone(coordinator)
    now_local = ensure_utc_time(dt_util.utcnow()).astimezone(local_tz)
    hour_start = now_local.replace(minute=0, second=0, microsecond=0)
    _current_period, _next_period, delta = get_current_and_next_price_periods(
        hour_start, zone_ceuta_melilla=coordinator.api.tariff != TARIFFS[0]
    )
    next_period_start = hour_start + delta
    delta_seconds = int((next_period_start - now_local).total_seconds())
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


def _local_timezone(coordinator: ElecPricesDataUpdateCoordinator):
    tz = dt_util.get_time_zone(coordinator.hass.config.time_zone)
    return tz or dt_util.UTC


def _price_range_for_timestamp(
    current_prices: dict[datetime, float],
    ts: datetime,
    local_tz,
) -> tuple[float, float] | None:
    target_date = ts.astimezone(local_tz).date()
    prices_for_date = [
        price
        for price_ts, price in current_prices.items()
        if price_ts.astimezone(local_tz).date() == target_date
    ]
    if not prices_for_date:
        return None
    return min(prices_for_date), max(prices_for_date)


def _price_ratio_for_timestamp(
    current_prices: dict[datetime, float],
    ts: datetime,
    price: float,
    local_tz,
) -> float | None:
    price_range = _price_range_for_timestamp(current_prices, ts, local_tz)
    if not price_range:
        return None
    min_price, max_price = price_range
    if max_price == min_price:
        return 0.6
    return round((price - min_price) / (max_price - min_price), 2)


def _next_price_candidate(
    coordinator: ElecPricesDataUpdateCoordinator,
) -> tuple[datetime, float] | None:
    current_prices = coordinator.data.sensors.get(KEY_PVPC, {})
    if not current_prices:
        return None
    now_utc = ensure_utc_time(dt_util.utcnow())
    current_hour = now_utc.replace(minute=0, second=0, microsecond=0)
    next_hour = current_hour + timedelta(hours=1)
    if next_hour in current_prices:
        return next_hour, current_prices[next_hour]
    next_ts = min((ts for ts in current_prices if ts > current_hour), default=None)
    if not next_ts:
        return None
    return next_ts, current_prices[next_ts]


def _next_price_value(
    coordinator: ElecPricesDataUpdateCoordinator,
) -> float | None:
    next_price = _next_price_candidate(coordinator)
    if not next_price:
        return None
    _ts, price = next_price
    return price


def _next_target_price(
    coordinator: ElecPricesDataUpdateCoordinator,
) -> tuple[datetime, float, float] | None:
    current_prices = coordinator.data.sensors.get(KEY_PVPC, {})
    if not current_prices:
        _log_debug_once_per_update(
            coordinator,
            "no_pvpc_prices",
            "No PVPC prices available; better-price sensors unavailable (entry_id=%s)",
            coordinator.entry_id,
        )
        return None
    now_utc = ensure_utc_time(dt_util.utcnow())
    target = normalize_better_price_target(coordinator.better_price_target)
    max_ratio = _PRICE_LEVEL_TARGET_MAX.get(target)
    if max_ratio is None:
        _log_debug_once_per_update(
            coordinator,
            "bad_target",
            "Unknown better price target '%s' (entry_id=%s)",
            target,
            coordinator.entry_id,
        )
    local_tz = _local_timezone(coordinator)
    candidates: list[tuple[datetime, float, float]] = []
    if max_ratio is not None:
        candidates = [
            (ts, price, ratio)
            for ts, price in current_prices.items()
            if ts > now_utc
            and (
                ratio := _price_ratio_for_timestamp(
                    current_prices, ts, price, local_tz
                )
            )
            is not None
            and ratio <= max_ratio
        ]
    if not candidates:
        fallback_candidates = [
            (ts, price, ratio)
            for ts, price in current_prices.items()
            if ts > now_utc
            and (ratio := _price_ratio_for_timestamp(current_prices, ts, price, local_tz))
            is not None
        ]
        if not fallback_candidates:
            future_prices = sum(1 for ts in current_prices if ts > now_utc)
            _log_debug_once_per_update(
                coordinator,
                "no_better_candidates",
                (
                    "No better-price candidates (target=%s max_ratio=%s "
                    "future_prices=%d total_prices=%d entry_id=%s)"
                ),
                target,
                f"{max_ratio:.2f}" if max_ratio is not None else "n/a",
                future_prices,
                len(current_prices),
                coordinator.entry_id,
            )
            return None
        fallback = min(fallback_candidates, key=lambda item: (item[1], item[0]))
        _log_debug_once_per_update(
            coordinator,
            "fallback_best_price",
            (
                "Fallback to best available price (target=%s max_ratio=%s "
                "ts=%s price=%.5f ratio=%.2f entry_id=%s)"
            ),
            target,
            f"{max_ratio:.2f}" if max_ratio is not None else "n/a",
            fallback[0].isoformat(),
            fallback[1],
            fallback[2],
            coordinator.entry_id,
        )
        return fallback
    next_target = min(candidates, key=lambda item: item[0])
    if _LOGGER.isEnabledFor(logging.DEBUG):
        soonest = sorted(candidates, key=lambda item: item[0])[:3]
        sample = ", ".join(
            f"{ts.isoformat()}@{price:.5f}/{ratio:.2f}"
            for ts, price, ratio in soonest
        )
        _log_debug_once_per_update(
            coordinator,
            "better_target",
            (
                "Better-price target=%s max_ratio=%.2f next=%s price=%.5f ratio=%.2f "
                "candidates=%d sample=[%s] entry_id=%s"
            ),
            target,
            max_ratio,
            next_target[0].isoformat(),
            next_target[1],
            next_target[2],
            len(candidates),
            sample,
            coordinator.entry_id,
        )
    return next_target


def _better_price_value(
    coordinator: ElecPricesDataUpdateCoordinator,
) -> StateType:
    current_prices = coordinator.data.sensors.get(KEY_PVPC, {})
    if not current_prices:
        return None
    next_target = _next_target_price(coordinator)
    if not next_target:
        return None
    _ts, price, _ratio = next_target
    return price


def _next_price_level(
    coordinator: ElecPricesDataUpdateCoordinator,
) -> str | None:
    next_price = _next_price_candidate(coordinator)
    if not next_price:
        return None
    ts, price = next_price
    current_prices = coordinator.data.sensors.get(KEY_PVPC, {})
    if not current_prices:
        return None
    local_tz = _local_timezone(coordinator)
    price_ratio = _price_ratio_for_timestamp(current_prices, ts, price, local_tz)
    if price_ratio is None:
        return None
    return _price_level_from_ratio(price_ratio)


def _better_price_level(
    coordinator: ElecPricesDataUpdateCoordinator,
) -> str | None:
    current_prices = coordinator.data.sensors.get(KEY_PVPC, {})
    if not current_prices:
        return None
    next_target = _next_target_price(coordinator)
    if not next_target:
        return None
    _ts, _price, ratio = next_target
    return _price_level_from_ratio(ratio)


def _price_level_from_ratio(price_ratio: float) -> str:
    for threshold, label in _PRICE_LEVEL_THRESHOLDS:
        if price_ratio <= threshold:
            return label
    return "very_expensive"


def _data_id_value(sensor_key: str) -> StateType:
    return SENSOR_KEY_TO_DATAID.get(sensor_key)


def _api_source_label(coordinator: ElecPricesDataUpdateCoordinator) -> str:
    return "private" if coordinator.api.using_private_api else "public"


def _log_debug_once_per_update(
    coordinator: ElecPricesDataUpdateCoordinator,
    key: str,
    message: str,
    *args,
) -> None:
    if not _LOGGER.isEnabledFor(logging.DEBUG):
        return
    last_update = getattr(coordinator.data, "last_update", None)
    if last_update is None:
        last_update = dt_util.utcnow()
    full_key = f"{key}:{coordinator.entry_id}"
    if _DEBUG_LAST_UPDATE.get(full_key) == last_update:
        return
    _DEBUG_LAST_UPDATE[full_key] = last_update
    _LOGGER.debug(message, *args)


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
        key="pvpc_api_source",
        name="API Source",
        value_fn=_api_source_label,
        icon="mdi:api",
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
        update_on_hour=True,
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_available_power",
        name="Available Power",
        attribute_key="available_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
        update_on_hour=True,
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_next_period",
        name="Next Period",
        attribute_key="next_period",
        icon="mdi:clock-outline",
        update_on_hour=True,
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_next_period_in",
        name="Next Period In",
        value_fn=_format_time_to_next_period,
        icon="mdi:timer-sand",
        update_every_minute=True,
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
        key="pvpc_next_best_price",
        name="Next Best Price",
        value_fn=_better_price_value,
        native_unit_of_measurement=_PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        icon="mdi:arrow-collapse-down",
        update_on_hour=True,
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_next_price",
        name="Next Price",
        value_fn=_next_price_value,
        native_unit_of_measurement=_PRICE_UNIT,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=5,
        icon="mdi:arrow-right-bold",
        update_on_hour=True,
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_next_price_in",
        name="Next Price In",
        value_fn=_format_time_to_next_price,
        update_every_minute=True,
        icon="mdi:clock-outline",
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_next_price_level",
        name="Next Price Level",
        value_fn=_next_price_level,
        device_class=SensorDeviceClass.ENUM,
        translation_key="price_level",
        update_every_minute=False,
        icon="mdi:scale-balance",
        update_on_hour=True,
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_time_to_next_best",
        name="Next Best In",
        value_fn=_format_time_to_better_price,
        update_every_minute=True,
        icon="mdi:clock-outline",
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_num_better_prices_ahead",
        name="Better Prices Ahead",
        attribute_key="num_better_prices_ahead",
        icon="mdi:counter",
        update_on_hour=True,
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_price_ratio_category",
        name="Current Price Level",
        value_fn=_price_ratio_category,
        device_class=SensorDeviceClass.ENUM,
        translation_key="price_level",
        update_every_minute=False,
        icon="mdi:scale-balance",
        update_on_hour=True,
    ),
    PVPCAttributeSensorDescription(
        key="pvpc_next_best_price_level",
        name="Next Best Level",
        value_fn=_better_price_level,
        device_class=SensorDeviceClass.ENUM,
        translation_key="price_level",
        update_every_minute=False,
        icon="mdi:scale-balance",
        update_on_hour=True,
    ),
)

PRIVATE_API_ATTRIBUTE_SENSOR_TYPES: tuple[PVPCAttributeSensorDescription, ...] = (
    PVPCAttributeSensorDescription(
        key="injection_price_data_id",
        name="Injection Price Data ID",
        value_fn=lambda _coordinator: _data_id_value(KEY_INJECTION),
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    PVPCAttributeSensorDescription(
        key="mag_tax_data_id",
        name="MAG Tax Data ID",
        value_fn=lambda _coordinator: _data_id_value(KEY_MAG),
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    PVPCAttributeSensorDescription(
        key="omie_price_data_id",
        name="OMIE Price Data ID",
        value_fn=lambda _coordinator: _data_id_value(KEY_OMIE),
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
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
    if entry.unique_id is None:
        _LOGGER.debug(
            "Config entry has no unique_id; falling back to entry_id (entry_id=%s)",
            entry.entry_id,
        )
    entry_unique_id = entry.unique_id or entry.entry_id
    config = {**entry.data, **entry.options}
    api_token = config.get(CONF_API_TOKEN)
    enable_private_api = config.get(ATTR_ENABLE_PRIVATE_API)
    if enable_private_api is None:
        enable_private_api = config.get(LEGACY_ATTR_ENABLE_INJECTION_PRICE)
    if enable_private_api is None:
        enable_private_api = (
            bool(api_token) if api_token else DEFAULT_ENABLE_PRIVATE_API
        )
    sensors = [ElecPriceSensor(coordinator, SENSOR_TYPES[0], entry_unique_id)]
    unique_id = entry_unique_id
    sensors.extend(
        PVPCAttributeSensor(coordinator, sensor_desc, unique_id)
        for sensor_desc in ATTRIBUTE_SENSOR_TYPES
    )
    if enable_private_api and coordinator.api.using_private_api:
        sensors.extend(
            PVPCAttributeSensor(coordinator, sensor_desc, unique_id)
            for sensor_desc in PRIVATE_API_ATTRIBUTE_SENSOR_TYPES
        )
    if coordinator.api.using_private_api:
        extra_sensors = []
        if enable_private_api:
            extra_sensors.extend(SENSOR_TYPES[1:])
        sensors.extend(
            ElecPriceSensor(coordinator, sensor_desc, entry_unique_id)
            for sensor_desc in extra_sensors
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
        elif self.entity_description.update_on_hour:
            self.async_on_remove(
                async_track_time_change(
                    self.hass, self._update_on_time_change, minute=[0], second=[0]
                )
            )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh immediately when coordinator data updates."""
        self.async_write_ha_state()

    @callback
    def _update_on_time_change(self, now: datetime) -> None:
        """Refresh state on time changes for time-based attributes."""
        if self.entity_description.update_on_hour:
            self.coordinator.api.process_state_and_attributes(
                self.coordinator.data, KEY_PVPC, now
            )
        self.async_write_ha_state()

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        if self.entity_description.value_fn is not None:
            return self.entity_description.value_fn(self.coordinator)
        attributes = self.coordinator.api.sensor_attributes.get(KEY_PVPC, {})
        if self.entity_description.key == "pvpc_num_better_prices_ahead":
            return attributes.get(self.entity_description.attribute_key, 0)
        return attributes.get(self.entity_description.attribute_key)
