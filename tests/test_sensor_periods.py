"""Tests for period helper calls in PVPC sensors."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from aiopvpc.const import KEY_PVPC
from homeassistant.const import CONF_NAME
from pytest_homeassistant_custom_component.common import MockConfigEntry

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
    DEFAULT_TARIFF,
    DEFAULT_UPDATE_FREQUENCY,
    DOMAIN,
)
from custom_components.pvpc_next.coordinator import ElecPricesDataUpdateCoordinator
from custom_components.pvpc_next.sensor import (
    _format_time_to_next_period,
    _format_time_to_next_power_period,
)


def _entry_data(holiday_source: str) -> dict:
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
        ATTR_HOLIDAY_SOURCE: holiday_source,
    }


def _coordinator(hass, holiday_source: str) -> ElecPricesDataUpdateCoordinator:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        unique_id=DEFAULT_TARIFF,
        data=_entry_data(holiday_source),
    )
    with patch("custom_components.pvpc_next.coordinator.PVPCData"):
        coordinator = ElecPricesDataUpdateCoordinator(
            hass, entry, sensor_keys=set(), use_private_api=False
        )
    coordinator.api.tariff = DEFAULT_TARIFF
    coordinator.data = SimpleNamespace(
        sensors={KEY_PVPC: {datetime(2026, 2, 3, 0, tzinfo=timezone.utc): 0.1}}
    )
    return coordinator


def test_next_period_uses_configured_holiday_source(hass) -> None:
    """Next period helper forwards configured holiday source."""
    coordinator = _coordinator(hass, "python-holidays")
    with (
        patch(
            "custom_components.pvpc_next.sensor.get_current_and_next_price_periods",
            return_value=("P1", "P2", timedelta(hours=1)),
        ) as mock_periods,
        patch(
            "custom_components.pvpc_next.sensor.dt_util.utcnow",
            return_value=datetime(2026, 2, 3, 10, 10, tzinfo=timezone.utc),
        ),
    ):
        _format_time_to_next_period(coordinator)

    assert mock_periods.call_args.kwargs["holiday_source"] == "python-holidays"


def test_next_power_period_uses_configured_holiday_source(hass) -> None:
    """Next power period helper forwards configured holiday source."""
    coordinator = _coordinator(hass, "csv")
    with (
        patch(
            "custom_components.pvpc_next.sensor.get_current_and_next_power_periods",
            return_value=("P1", "P3", timedelta(hours=1)),
        ) as mock_periods,
        patch(
            "custom_components.pvpc_next.sensor.dt_util.utcnow",
            return_value=datetime(2026, 2, 3, 10, 10, tzinfo=timezone.utc),
        ),
    ):
        _format_time_to_next_power_period(coordinator)

    assert mock_periods.call_args.kwargs["holiday_source"] == "csv"
