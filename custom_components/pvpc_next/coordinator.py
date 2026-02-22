"""The PVPC Next integration to collect Spain official electric prices."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .aiopvpc import BadApiTokenAuthError, DEFAULT_POWER_KW, EsiosApiData, PVPCData
from .aiopvpc.const import SENSOR_KEY_TO_DATAID
from .const import (
    ATTR_POWER_P1,
    ATTR_POWER_P3,
    ATTR_BETTER_PRICE_TARGET,
    ATTR_HOLIDAY_SOURCE,
    ATTR_PRICE_MODE,
    ATTR_TARIFF,
    DOMAIN,
    DEFAULT_BETTER_PRICE_TARGET,
    DEFAULT_HOLIDAY_SOURCE,
    DEFAULT_PRICE_MODE,
    LEGACY_ATTR_POWER,
    LEGACY_ATTR_POWER_P2_P3,
    LEGACY_ATTR_POWER_P3,
    normalize_better_price_target,
    normalize_holiday_source,
    normalize_price_mode,
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
        configured_price_mode = normalize_price_mode(
            config.get(ATTR_PRICE_MODE, DEFAULT_PRICE_MODE)
        )
        effective_price_mode = (
            configured_price_mode
            if configured_price_mode != "indexed" or use_private_api
            else "pvpc"
        )
        api_token = config.get(CONF_API_TOKEN) if use_private_api else None
        self._holiday_source = holiday_source
        self._configured_price_mode = configured_price_mode
        self._price_mode = effective_price_mode
        if configured_price_mode == "indexed" and not use_private_api:
            _LOGGER.warning(
                "Indexed mode requested but private API is disabled; falling back to PVPC mode"
            )

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

    @property
    def holiday_source(self) -> str:
        """Return configured holiday source."""
        return self._holiday_source

    @property
    def price_mode(self) -> str:
        """Return effective price mode."""
        return self._price_mode

    @property
    def configured_price_mode(self) -> str:
        """Return configured price mode."""
        return self._configured_price_mode

    async def _async_update_data(self) -> EsiosApiData:
        """Update electricity prices from the ESIOS API."""
        now = dt_util.utcnow()
        try:
            api_data = await self.api.async_update_all(self.data, now)
        except BadApiTokenAuthError as exc:
            raise ConfigEntryAuthFailed from exc
        if (
            not api_data
            or not api_data.sensors
            or not any(api_data.availability.values())
        ):
            raise UpdateFailed
        self._log_api_fetch(api_data, now)
        return api_data

    def _log_api_fetch(self, api_data: EsiosApiData, now: datetime) -> None:
        """Log fetched API payload details when debug logging is enabled."""
        if not _LOGGER.isEnabledFor(logging.DEBUG):
            return

        fetched_keys = sorted(
            key for key, available in api_data.availability.items() if available
        )
        unavailable_keys = sorted(
            key for key, available in api_data.availability.items() if not available
        )
        indicator_ids = {
            key: SENSOR_KEY_TO_DATAID.get(key, "n/a") for key in fetched_keys
        }
        _LOGGER.debug(
            "PVPC API fetch source=%s private=%s holiday_source=%s at=%s "
            "fetched_keys=%s unavailable_keys=%s indicator_ids=%s",
            api_data.data_source,
            self.api.using_private_api,
            self._holiday_source,
            now.isoformat(),
            fetched_keys,
            unavailable_keys,
            indicator_ids,
        )

        for key in fetched_keys:
            series = api_data.sensors.get(key, {})
            if not series:
                _LOGGER.debug("PVPC API fetch series=%s points=0", key)
                continue
            first_ts = min(series)
            last_ts = max(series)
            min_price = min(series.values())
            max_price = max(series.values())
            data_id = self.api.sensor_attributes.get(key, {}).get("data_id")
            _LOGGER.debug(
                "PVPC API fetch series=%s data_id=%s points=%d first=%s last=%s "
                "min=%.5f max=%.5f",
                key,
                data_id,
                len(series),
                first_ts.isoformat(),
                last_ts.isoformat(),
                min_price,
                max_price,
            )
