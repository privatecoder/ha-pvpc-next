"""The PVPC Next integration to collect Spain official electric prices."""
from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from aiopvpc import BadApiTokenAuthError, DEFAULT_POWER_KW, EsiosApiData, PVPCData
from .const import (
    ATTR_POWER_P1,
    ATTR_POWER_P3,
    ATTR_BETTER_PRICE_TARGET,
    ATTR_HOLIDAY_SOURCE,
    ATTR_TARIFF,
    DOMAIN,
    DEFAULT_BETTER_PRICE_TARGET,
    DEFAULT_HOLIDAY_SOURCE,
    LEGACY_ATTR_POWER,
    LEGACY_ATTR_POWER_P2_P3,
    LEGACY_ATTR_POWER_P3,
    normalize_better_price_target,
    normalize_holiday_source,
)

_LOGGER = logging.getLogger(__name__)

PVPCConfigEntry = ConfigEntry["ElecPricesDataUpdateCoordinator"]


class ElecPricesDataUpdateCoordinator(  # pylint: disable=too-few-public-methods
    DataUpdateCoordinator[EsiosApiData]
):
    """Class to manage fetching Electricity prices data from API."""

    config_entry: PVPCConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: PVPCConfigEntry,
        sensor_keys: set[str],
        use_private_api: bool,
    ) -> None:
        """Initialize."""
        config = {**entry.data, **entry.options}

        power_p1 = config.get(ATTR_POWER_P1, config.get(LEGACY_ATTR_POWER))
        power_p3 = config.get(
            ATTR_POWER_P3,
            config.get(LEGACY_ATTR_POWER_P2_P3, config.get(LEGACY_ATTR_POWER_P3)),
        )
        better_price_target = normalize_better_price_target(
            config.get(ATTR_BETTER_PRICE_TARGET, DEFAULT_BETTER_PRICE_TARGET)
        )
        if power_p1 is None:
            power_p1 = DEFAULT_POWER_KW
        if power_p3 is None:
            power_p3 = DEFAULT_POWER_KW
        holiday_source = normalize_holiday_source(
            config.get(ATTR_HOLIDAY_SOURCE, DEFAULT_HOLIDAY_SOURCE)
        )
        api_token = config.get(CONF_API_TOKEN) if use_private_api else None

        self.api = PVPCData(
            session=async_get_clientsession(hass),
            tariff=config[ATTR_TARIFF],
            local_timezone=hass.config.time_zone,
            power=power_p1,
            power_valley=power_p3,
            api_token=api_token,
            holiday_source=holiday_source,
            sensor_keys=tuple(sensor_keys),
        )
        self._better_price_target = better_price_target
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(minutes=30),
        )

    @property
    def entry_id(self) -> str:
        """Return entry ID."""
        return self.config_entry.entry_id

    @property
    def better_price_target(self) -> str:
        """Return canonical better-price target label."""
        return self._better_price_target

    async def _async_update_data(self) -> EsiosApiData:
        """Update electricity prices from the ESIOS API."""
        try:
            api_data = await self.api.async_update_all(self.data, dt_util.utcnow())
        except BadApiTokenAuthError as exc:
            raise ConfigEntryAuthFailed from exc
        if (
            not api_data
            or not api_data.sensors
            or not any(api_data.availability.values())
        ):
            raise UpdateFailed
        return api_data
