"""Tests for indexed price sensor wiring."""

from unittest.mock import AsyncMock, patch

from aiopvpc.const import KEY_ADJUSTMENT, KEY_INDEXED
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
    ATTR_PRICE_MODE,
    ATTR_SHOW_REFERENCE_PRICE,
    ATTR_POWER_P1,
    ATTR_POWER_P3,
    ATTR_TARIFF,
    DEFAULT_BETTER_PRICE_TARGET,
    DEFAULT_HOLIDAY_SOURCE,
    DEFAULT_TARIFF,
    DEFAULT_UPDATE_FREQUENCY,
    DOMAIN,
)
from custom_components.pvpc_next.coordinator import ElecPricesDataUpdateCoordinator
from custom_components.pvpc_next.helpers import make_sensor_unique_id
from custom_components.pvpc_next.sensor import ElecPriceSensor, async_setup_entry


def _entry_data() -> dict:
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
        ATTR_PRICE_MODE: "pvpc",
        ATTR_SHOW_REFERENCE_PRICE: True,
        CONF_API_TOKEN: "token",
    }


def test_make_sensor_unique_id_supports_indexed() -> None:
    """Indexed sensor key should be accepted for unique_id generation."""
    assert make_sensor_unique_id("2.0TD", KEY_INDEXED) == "2.0TD_INDEXED"


async def test_reference_indexed_sensor_is_created_and_requests_adjustment(hass) -> None:
    """PVPC mode should expose Current Indexed Price and fetch ADJUSTMENT series."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        unique_id=DEFAULT_TARIFF,
        data=_entry_data(),
    )

    with patch("custom_components.pvpc_next.coordinator.PVPCData"):
        coordinator = ElecPricesDataUpdateCoordinator(
            hass, entry, sensor_keys=set(), use_private_api=True
        )

    coordinator.api.using_private_api = True
    coordinator.api.update_active_sensors.reset_mock()
    coordinator.async_request_refresh = AsyncMock()
    entry.runtime_data = coordinator

    added_entities = []

    def _add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(hass, entry, _add_entities)

    indexed_entity = next(
        entity
        for entity in added_entities
        if isinstance(entity, ElecPriceSensor)
        and entity.entity_description.key == KEY_INDEXED
    )

    indexed_entity.hass = hass
    with patch.object(hass, "async_create_task") as mock_create_task:
        await indexed_entity.async_added_to_hass()

    coordinator.api.update_active_sensors.assert_any_call(KEY_ADJUSTMENT, True)
    mock_create_task.assert_called_once()
