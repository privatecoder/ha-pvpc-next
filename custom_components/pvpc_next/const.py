"""Constant values for PVPC Next."""

import voluptuous as vol

from .aiopvpc.const import TARIFFS

DOMAIN = "pvpc_next"

ATTR_POWER_P1 = "power_p1"
ATTR_POWER_P3 = "power_p3"
ATTR_BETTER_PRICE_TARGET = "better_price_target"
ATTR_ENABLE_PRIVATE_API = "enable_private_api"
ATTR_PRICE_MODE = "price_mode"
ATTR_SHOW_REFERENCE_PRICE = "show_reference_price"
ATTR_HOLIDAY_SOURCE = "holiday_source"
LEGACY_ATTR_ENABLE_INJECTION_PRICE = "enable_injection_price"
LEGACY_ATTR_POWER = "power"
LEGACY_ATTR_POWER_P2_P3 = "power_p2_p3"
LEGACY_ATTR_POWER_P3 = "power_p3"
ATTR_NEXT_PRICE_IN_UPDATE = "next_price_in_update"
ATTR_NEXT_BEST_IN_UPDATE = "next_best_in_update"
ATTR_NEXT_PERIOD_IN_UPDATE = "next_period_in_update"
ATTR_NEXT_POWER_PERIOD_IN_UPDATE = "next_power_period_in_update"
ATTR_TARIFF = "tariff"
DEFAULT_NAME = "PVPC Next"
DEFAULT_TARIFF = TARIFFS[0]

DEFAULT_BETTER_PRICE_TARGET = "very cheap"
DEFAULT_ENABLE_PRIVATE_API = False
DEFAULT_PRICE_MODE = "pvpc"
DEFAULT_SHOW_REFERENCE_PRICE = False
BETTER_PRICE_TARGETS = ("neutral", "cheap", "very cheap")
PRICE_MODES = ("pvpc", "indexed")
HOLIDAY_SOURCES = ("csv", "python-holidays")
UPDATE_FREQUENCY_OPTIONS = ("disabled", "hourly", "minute")
DEFAULT_UPDATE_FREQUENCY = "minute"
DEFAULT_HOLIDAY_SOURCE = "csv"
UPDATE_FREQUENCY_BY_SENSOR = {
    "pvpc_next_price_in": ATTR_NEXT_PRICE_IN_UPDATE,
    "pvpc_time_to_next_best": ATTR_NEXT_BEST_IN_UPDATE,
    "pvpc_next_period_in": ATTR_NEXT_PERIOD_IN_UPDATE,
    "pvpc_next_power_period_in": ATTR_NEXT_POWER_PERIOD_IN_UPDATE,
}
VALID_POWER = vol.All(vol.Coerce(float), vol.Range(min=1.0, max=15.0))
VALID_TARIFF = vol.In(TARIFFS)
VALID_BETTER_PRICE_TARGET = vol.In(BETTER_PRICE_TARGETS)
VALID_PRICE_MODE = vol.In(PRICE_MODES)


def normalize_better_price_target(target: str | None) -> str:
    """Return canonical better-price target label."""
    if not target:
        return DEFAULT_BETTER_PRICE_TARGET
    mapping = {
        "very cheap": "very_cheap",
        "very_cheap": "very_cheap",
        "cheap": "cheap",
        "neutral": "neutral",
    }
    return mapping.get(target, DEFAULT_BETTER_PRICE_TARGET)


def normalize_holiday_source(source: str | None) -> str:
    """Return canonical holiday source label."""
    if not source:
        return DEFAULT_HOLIDAY_SOURCE
    if source in HOLIDAY_SOURCES:
        return source
    return DEFAULT_HOLIDAY_SOURCE


def normalize_price_mode(mode: str | None) -> str:
    """Return canonical price mode label."""
    if not mode:
        return DEFAULT_PRICE_MODE
    if mode in PRICE_MODES:
        return mode
    return DEFAULT_PRICE_MODE
