"""Constant values for PVPC Next."""

import voluptuous as vol

from .aiopvpc.const import TARIFFS

DOMAIN = "pvpc_next"

ATTR_POWER_P1 = "power_p1"
ATTR_POWER_P2_P3 = "power_p2_p3"
LEGACY_ATTR_POWER = "power"
LEGACY_ATTR_POWER_P3 = "power_p3"
ATTR_TARIFF = "tariff"
DEFAULT_NAME = "PVPC Next"
CONF_USE_API_TOKEN = "use_api_token"

VALID_POWER = vol.All(vol.Coerce(float), vol.Range(min=1.0, max=15.0))
VALID_TARIFF = vol.In(TARIFFS)
DEFAULT_TARIFF = TARIFFS[0]
