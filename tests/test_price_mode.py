"""Tests for price mode behavior."""

from types import SimpleNamespace
from unittest.mock import patch

from custom_components.pvpc_next.aiopvpc.const import KEY_INDEXED, KEY_PVPC
from homeassistant.const import CONF_API_TOKEN, CONF_NAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pvpc_next.const import (
    ATTR_BETTER_PRICE_TARGET,
    ATTR_ENABLE_PRIVATE_API,
    ATTR_HOLIDAY_SOURCE,
    ATTR_NEXT_BEST_IN_UPDATE,
    ATTR_NEXT_PERIOD_IN_UPDATE,
    ATTR_NEXT_POWER_PERIOD_IN_UPDATE,
    ATTR_NEXT_PRICE_IN_UPDATE,
    ATTR_SHOW_REFERENCE_PRICE,
    ATTR_POWER_P1,
    ATTR_POWER_P3,
    ATTR_PRICE_MODE,
    ATTR_TARIFF,
    DEFAULT_BETTER_PRICE_TARGET,
    DEFAULT_HOLIDAY_SOURCE,
    DEFAULT_TARIFF,
    DEFAULT_UPDATE_FREQUENCY,
    DOMAIN,
)
from custom_components.pvpc_next.coordinator import ElecPricesDataUpdateCoordinator
from custom_components.pvpc_next.sensor import (
    ATTRIBUTE_SENSOR_TYPES,
    SENSOR_TYPES,
    ElecPriceSensor,
    PVPCAttributeSensor,
    async_setup_entry,
)


def _entry_data(price_mode: str = "pvpc", show_reference_price: bool = False) -> dict:
    return {
        CONF_NAME: "PVPC Test",
        ATTR_TARIFF: DEFAULT_TARIFF,
        ATTR_POWER_P1: 4.4,
        ATTR_POWER_P3: 3.3,
        ATTR_BETTER_PRICE_TARGET: DEFAULT_BETTER_PRICE_TARGET,
        ATTR_NEXT_PRICE_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
        ATTR_NEXT_BEST_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
        ATTR_NEXT_PERIOD_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
        ATTR_NEXT_POWER_PERIOD_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
        ATTR_HOLIDAY_SOURCE: DEFAULT_HOLIDAY_SOURCE,
        ATTR_ENABLE_PRIVATE_API: True,
        ATTR_PRICE_MODE: price_mode,
        ATTR_SHOW_REFERENCE_PRICE: show_reference_price,
        CONF_API_TOKEN: "token",
    }


def test_current_price_uses_indexed_series_when_mode_is_indexed(hass):
    """Current Price should read indexed state/attributes in indexed mode."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        unique_id=DEFAULT_TARIFF,
        data=_entry_data(price_mode="indexed"),
    )
    with patch("custom_components.pvpc_next.coordinator.PVPCData"):
        coordinator = ElecPricesDataUpdateCoordinator(
            hass, entry, sensor_keys=set(), use_private_api=True
        )

    coordinator.data = SimpleNamespace(availability={KEY_INDEXED: True, KEY_PVPC: True})
    coordinator.api.states = {KEY_INDEXED: 0.12345}
    coordinator.api.sensor_attributes = {KEY_INDEXED: {"price_position": 1}}

    sensor = ElecPriceSensor(coordinator, SENSOR_TYPES[0], DEFAULT_TARIFF)

    assert sensor.available is True
    assert sensor.native_value == 0.12345
    assert sensor.extra_state_attributes["mode"] == "indexed"
    assert sensor.extra_state_attributes["price_position"] == 1


def test_price_mode_diagnostic_sensor_reports_effective_mode(hass):
    """Price mode diagnostic sensor should expose effective mode label."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        unique_id=DEFAULT_TARIFF,
        data=_entry_data(price_mode="indexed"),
    )
    with patch("custom_components.pvpc_next.coordinator.PVPCData"):
        coordinator = ElecPricesDataUpdateCoordinator(
            hass, entry, sensor_keys=set(), use_private_api=True
        )

    coordinator.data = SimpleNamespace(availability={KEY_PVPC: True})
    desc = next(item for item in ATTRIBUTE_SENSOR_TYPES if item.key == "pvpc_price_mode")
    sensor = PVPCAttributeSensor(coordinator, desc, DEFAULT_TARIFF)

    assert sensor.native_value == "indexed"


async def test_reference_sensor_current_indexed_in_pvpc_mode(hass):
    """PVPC mode exposes Current Indexed Price when show_reference_price is enabled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        unique_id=DEFAULT_TARIFF,
        data=_entry_data(price_mode="pvpc", show_reference_price=True),
    )
    with patch("custom_components.pvpc_next.coordinator.PVPCData"):
        coordinator = ElecPricesDataUpdateCoordinator(
            hass, entry, sensor_keys=set(), use_private_api=True
        )
    coordinator.api.using_private_api = True
    entry.runtime_data = coordinator
    added_entities = []
    await async_setup_entry(hass, entry, added_entities.extend)

    names = [
        entity.entity_description.name
        for entity in added_entities
        if isinstance(entity, ElecPriceSensor)
    ]
    assert "Current Indexed Price" in names
    assert "Current PVPC" not in names


async def test_reference_sensor_current_pvpc_in_indexed_mode(hass):
    """Indexed mode exposes Current PVPC when show_reference_price is enabled."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        unique_id=DEFAULT_TARIFF,
        data=_entry_data(price_mode="indexed", show_reference_price=True),
    )
    with patch("custom_components.pvpc_next.coordinator.PVPCData"):
        coordinator = ElecPricesDataUpdateCoordinator(
            hass, entry, sensor_keys=set(), use_private_api=True
        )
    coordinator.api.using_private_api = True
    entry.runtime_data = coordinator
    added_entities = []
    await async_setup_entry(hass, entry, added_entities.extend)

    names = [
        entity.entity_description.name
        for entity in added_entities
        if isinstance(entity, ElecPriceSensor)
    ]
    assert "Current PVPC" in names
    assert "Current Indexed Price" not in names
