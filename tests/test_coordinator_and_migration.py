"""Tests for PVPC client creation and entry migration."""

from datetime import datetime, timezone
import logging
from unittest.mock import patch

from aiopvpc.const import EsiosApiData
from homeassistant.const import CONF_NAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.pvpc_next import async_migrate_entry
from custom_components.pvpc_next.const import (
    ATTR_BETTER_PRICE_TARGET,
    ATTR_ENABLE_PRIVATE_API,
    ATTR_HOLIDAY_SOURCE,
    ATTR_NEXT_BEST_IN_UPDATE,
    ATTR_NEXT_PERIOD_IN_UPDATE,
    ATTR_NEXT_POWER_PERIOD_IN_UPDATE,
    ATTR_NEXT_PRICE_IN_UPDATE,
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
        ATTR_ENABLE_PRIVATE_API: False,
    }


def test_coordinator_passes_holiday_source_to_pvpc_client(hass):
    """Coordinator passes configured holiday source to PVPCData."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        unique_id=DEFAULT_TARIFF,
        data={**_entry_data(), ATTR_HOLIDAY_SOURCE: "csv"},
    )

    with patch("custom_components.pvpc_next.coordinator.PVPCData") as mock_pvpc_data:
        ElecPricesDataUpdateCoordinator(
            hass, entry, sensor_keys=set(), use_private_api=False
        )

    assert mock_pvpc_data.call_args.kwargs["holiday_source"] == "csv"


def test_coordinator_uses_current_holiday_default(hass):
    """Coordinator uses csv if holiday source is not configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        unique_id=DEFAULT_TARIFF,
        data=_entry_data(),
    )

    with patch("custom_components.pvpc_next.coordinator.PVPCData") as mock_pvpc_data:
        ElecPricesDataUpdateCoordinator(
            hass, entry, sensor_keys=set(), use_private_api=False
        )

    assert mock_pvpc_data.call_args.kwargs["holiday_source"] == DEFAULT_HOLIDAY_SOURCE


async def test_migration_sets_holiday_source_for_existing_entries(hass):
    """Migration upgrades to v7 and sets default holiday source."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        version=6,
        unique_id=DEFAULT_TARIFF,
        data=_entry_data(),
    )
    entry.add_to_hass(hass)

    assert await async_migrate_entry(hass, entry)
    assert entry.version == 7
    assert entry.data[ATTR_HOLIDAY_SOURCE] == DEFAULT_HOLIDAY_SOURCE


def test_log_api_fetch_includes_source_and_series_details(hass, caplog):
    """Debug logs include fetched source and per-series payload details."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        unique_id=DEFAULT_TARIFF,
        data={**_entry_data(), ATTR_HOLIDAY_SOURCE: "csv"},
    )
    coordinator = ElecPricesDataUpdateCoordinator(
        hass, entry, sensor_keys=set(), use_private_api=False
    )
    coordinator.api.sensor_attributes["PVPC"] = {"data_id": "1001"}
    api_data = EsiosApiData(
        last_update=datetime(2026, 1, 2, tzinfo=timezone.utc),
        data_source="esios_public",
        sensors={
            "PVPC": {
                datetime(2026, 1, 2, 0, tzinfo=timezone.utc): 0.12345,
                datetime(2026, 1, 2, 1, tzinfo=timezone.utc): 0.23456,
            }
        },
        availability={"PVPC": True},
    )

    with caplog.at_level(
        logging.DEBUG, logger="custom_components.pvpc_next.coordinator"
    ):
        coordinator._log_api_fetch(
            api_data, datetime(2026, 1, 2, 2, tzinfo=timezone.utc)
        )

    assert "source=esios_public" in caplog.text
    assert "fetched_keys=['PVPC']" in caplog.text
    assert "series=PVPC data_id=1001 points=2" in caplog.text
