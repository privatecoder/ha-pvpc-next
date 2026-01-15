"""Constant values for PVPC Next."""

import voluptuous as vol

from .aiopvpc.const import TARIFFS

DOMAIN = "pvpc_next"

ATTR_POWER_P1 = "power_p1"
ATTR_POWER_P2_P3 = "power_p2_p3"
ATTR_BETTER_PRICE_TARGET = "better_price_target"
ATTR_ENABLE_INJECTION_PRICE = "enable_injection_price"
LEGACY_ATTR_POWER = "power"
LEGACY_ATTR_POWER_P3 = "power_p3"
ATTR_TARIFF = "tariff"
DEFAULT_NAME = "PVPC Next"
CONF_USE_API_TOKEN = "use_api_token"
DEFAULT_TARIFF = TARIFFS[0]

DEFAULT_BETTER_PRICE_TARGET = "neutral"
DEFAULT_ENABLE_INJECTION_PRICE = False
BETTER_PRICE_TARGETS = ("neutral", "cheap", "very cheap")
VALID_POWER = vol.All(vol.Coerce(float), vol.Range(min=1.0, max=15.0))
VALID_TARIFF = vol.In(TARIFFS)
VALID_BETTER_PRICE_TARGET = vol.In(BETTER_PRICE_TARGETS)


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
