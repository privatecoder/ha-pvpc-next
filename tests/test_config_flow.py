"""Tests for PVPC Next config and options flows."""

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_TOKEN, CONF_NAME
from homeassistant.data_entry_flow import FlowResultType
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
    DEFAULT_PRICE_MODE,
    DEFAULT_TARIFF,
    DEFAULT_UPDATE_FREQUENCY,
    DOMAIN,
)


async def test_user_flow_persists_holiday_source(hass):
    """User flow stores selected holiday source in config entry data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "PVPC Test",
            ATTR_TARIFF: DEFAULT_TARIFF,
            ATTR_POWER_P1: 4.4,
            ATTR_POWER_P3: 3.3,
            ATTR_BETTER_PRICE_TARGET: DEFAULT_BETTER_PRICE_TARGET,
            ATTR_NEXT_PRICE_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_NEXT_BEST_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_NEXT_PERIOD_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_NEXT_POWER_PERIOD_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_HOLIDAY_SOURCE: "csv",
            ATTR_ENABLE_PRIVATE_API: False,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][ATTR_HOLIDAY_SOURCE] == "csv"
    assert result["data"][ATTR_PRICE_MODE] == DEFAULT_PRICE_MODE


async def test_options_flow_persists_holiday_source(hass):
    """Options flow stores selected holiday source in options data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        unique_id=DEFAULT_TARIFF,
        data={
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
            ATTR_ENABLE_PRIVATE_API: False,
            ATTR_PRICE_MODE: DEFAULT_PRICE_MODE,
            ATTR_SHOW_REFERENCE_PRICE: False,
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            ATTR_POWER_P1: 5.0,
            ATTR_POWER_P3: 4.0,
            ATTR_BETTER_PRICE_TARGET: DEFAULT_BETTER_PRICE_TARGET,
            ATTR_NEXT_PRICE_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_NEXT_BEST_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_NEXT_PERIOD_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_NEXT_POWER_PERIOD_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_HOLIDAY_SOURCE: "csv",
            ATTR_ENABLE_PRIVATE_API: False,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][ATTR_HOLIDAY_SOURCE] == "csv"
    assert result["data"][ATTR_PRICE_MODE] == DEFAULT_PRICE_MODE


async def test_options_flow_private_api_exposes_mode_step(hass):
    """Options flow should ask for mode when private API is enabled with token."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="PVPC Test",
        unique_id=DEFAULT_TARIFF,
        data={
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
            ATTR_PRICE_MODE: DEFAULT_PRICE_MODE,
            ATTR_SHOW_REFERENCE_PRICE: False,
            CONF_API_TOKEN: "token",
        },
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            ATTR_POWER_P1: 5.0,
            ATTR_POWER_P3: 4.0,
            ATTR_BETTER_PRICE_TARGET: DEFAULT_BETTER_PRICE_TARGET,
            ATTR_NEXT_PRICE_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_NEXT_BEST_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_NEXT_PERIOD_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_NEXT_POWER_PERIOD_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_HOLIDAY_SOURCE: "csv",
            ATTR_ENABLE_PRIVATE_API: True,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "price_mode"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={ATTR_PRICE_MODE: "indexed", ATTR_SHOW_REFERENCE_PRICE: True},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][ATTR_PRICE_MODE] == "indexed"
    assert result["data"][ATTR_SHOW_REFERENCE_PRICE] is True


async def test_user_flow_private_api_token_enables_indexed_mode_step(hass):
    """Private API setup should expose mode selection after valid token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_NAME: "PVPC Test",
            ATTR_TARIFF: DEFAULT_TARIFF,
            ATTR_POWER_P1: 4.4,
            ATTR_POWER_P3: 3.3,
            ATTR_BETTER_PRICE_TARGET: DEFAULT_BETTER_PRICE_TARGET,
            ATTR_NEXT_PRICE_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_NEXT_BEST_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_NEXT_PERIOD_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_NEXT_POWER_PERIOD_IN_UPDATE: DEFAULT_UPDATE_FREQUENCY,
            ATTR_HOLIDAY_SOURCE: "csv",
            ATTR_ENABLE_PRIVATE_API: True,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "api_token"

    with patch(
        "custom_components.pvpc_next.config_flow.PVPCData.check_api_token",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_TOKEN: "token"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "price_mode"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={ATTR_PRICE_MODE: "indexed", ATTR_SHOW_REFERENCE_PRICE: True},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][ATTR_ENABLE_PRIVATE_API] is True
    assert result["data"][ATTR_PRICE_MODE] == "indexed"
    assert result["data"][ATTR_SHOW_REFERENCE_PRICE] is True
