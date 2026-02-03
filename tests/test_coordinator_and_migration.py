"""Tests for PVPC client creation and entry migration."""

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from unittest.mock import AsyncMock

import pytest
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


async def test_csv_source_warms_holiday_cache_in_executor(hass):
    """CSV source warms current-year holiday cache once before update."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        unique_id=DEFAULT_TARIFF,
        data={**_entry_data(), ATTR_HOLIDAY_SOURCE: "csv"},
    )
    coordinator = ElecPricesDataUpdateCoordinator(
        hass, entry, sensor_keys=set(), use_private_api=False
    )
    api_data = SimpleNamespace(
        sensors={"pvpc": object()}, availability={"pvpc": True}
    )
    coordinator.api.async_update_all = AsyncMock(side_effect=[api_data, api_data])
    current_year = 2026

    with (
        patch(
            "custom_components.pvpc_next.coordinator._warm_aiopvpc_holidays"
        ) as mock_warm,
        patch(
            "custom_components.pvpc_next.coordinator.dt_util.utcnow",
            return_value=datetime(2026, 2, 10, tzinfo=timezone.utc),
        ),
    ):
        await coordinator._async_update_data()
        await coordinator._async_update_data()

    assert mock_warm.call_count == 1
    mock_warm.assert_called_once_with(current_year, "csv")


async def test_csv_source_retries_until_jan_six_with_provisional_cache(hass):
    """CSV source retries current-year fetch and primes provisional cache on failure."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        unique_id=DEFAULT_TARIFF,
        data={**_entry_data(), ATTR_HOLIDAY_SOURCE: "csv"},
    )
    coordinator = ElecPricesDataUpdateCoordinator(
        hass, entry, sensor_keys=set(), use_private_api=False
    )

    with (
        patch(
            "custom_components.pvpc_next.coordinator._warm_aiopvpc_holidays",
            side_effect=[RuntimeError("fetch failed"), None],
        ) as mock_warm,
        patch(
            "custom_components.pvpc_next.coordinator._prime_aiopvpc_holiday_cache"
        ) as mock_prime,
        patch(
            "custom_components.pvpc_next.coordinator._clear_aiopvpc_holiday_cache"
        ) as mock_clear,
    ):
        await coordinator._async_warm_holiday_cache(
            datetime(2026, 1, 1, tzinfo=timezone.utc)
        )
        await coordinator._async_warm_holiday_cache(
            datetime(2026, 1, 5, tzinfo=timezone.utc)
        )

        assert mock_warm.call_count == 2
        assert mock_prime.call_count == 1
        mock_clear.assert_called_once()
        mock_prime.assert_called_once_with(
            2026, "csv", {date(2026, 1, 1), date(2026, 1, 6)}
        )

        await coordinator._async_warm_holiday_cache(
            datetime(2026, 1, 6, tzinfo=timezone.utc)
        )

    assert mock_warm.call_count == 2


async def test_csv_source_raises_after_jan_six_if_fetch_still_fails(hass):
    """CSV source does not silently suppress current-year fetch failures after Jan 6."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        unique_id=DEFAULT_TARIFF,
        data={**_entry_data(), ATTR_HOLIDAY_SOURCE: "csv"},
    )
    coordinator = ElecPricesDataUpdateCoordinator(
        hass, entry, sensor_keys=set(), use_private_api=False
    )

    with patch(
        "custom_components.pvpc_next.coordinator._warm_aiopvpc_holidays",
        side_effect=RuntimeError("fetch failed"),
    ):
        with pytest.raises(RuntimeError):
            await coordinator._async_warm_holiday_cache(
                datetime(2026, 1, 7, tzinfo=timezone.utc)
            )


async def test_non_csv_source_skips_holiday_cache_warmup(hass):
    """Non-csv source does not run cache warmup."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        unique_id=DEFAULT_TARIFF,
        data={**_entry_data(), ATTR_HOLIDAY_SOURCE: "python-holidays"},
    )
    coordinator = ElecPricesDataUpdateCoordinator(
        hass, entry, sensor_keys=set(), use_private_api=False
    )
    api_data = SimpleNamespace(
        sensors={"pvpc": object()}, availability={"pvpc": True}
    )
    coordinator.api.async_update_all = AsyncMock(return_value=api_data)

    with patch(
        "custom_components.pvpc_next.coordinator._warm_aiopvpc_holidays"
    ) as mock_holidays:
        await coordinator._async_update_data()

    assert mock_holidays.call_count == 0
