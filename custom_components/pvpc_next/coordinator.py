"""The PVPC Next integration to collect Spain official electric prices."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

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


def _warm_aiopvpc_holidays(year: int, source: str) -> None:
    """Warm aiopvpc cached holidays for one year."""
    from aiopvpc.pvpc_tariff import _national_p3_holidays

    _national_p3_holidays(year, source)


def _clear_aiopvpc_holiday_cache() -> None:
    """Clear aiopvpc holiday cache."""
    from aiopvpc.pvpc_tariff import _national_p3_holidays

    _national_p3_holidays.cache_clear()


def _prime_aiopvpc_holiday_cache(
    year: int, source: str, provisional_holidays: set[date]
) -> None:
    """Prime aiopvpc current-year cache with provisional holidays."""
    import aiopvpc.pvpc_tariff as pvpc_tariff

    original_get_pvpc_holidays = pvpc_tariff.get_pvpc_holidays

    def _provisional_get_pvpc_holidays(target_year: int, source: str = source):
        if target_year == year:
            return {day: "provisional" for day in provisional_holidays}
        return original_get_pvpc_holidays(target_year, source=source)

    pvpc_tariff.get_pvpc_holidays = _provisional_get_pvpc_holidays
    pvpc_tariff._national_p3_holidays.cache_clear()
    try:
        pvpc_tariff._national_p3_holidays(year, source)
    finally:
        pvpc_tariff.get_pvpc_holidays = original_get_pvpc_holidays


def _provisional_january_holidays(year: int) -> set[date]:
    """Return provisional Jan 1 / Jan 6 holidays for one year (weekdays only)."""
    holidays: set[date] = set()
    for month, day in ((1, 1), (1, 6)):
        holiday = date(year, month, day)
        if holiday.weekday() < 5:
            holidays.add(holiday)
    return holidays


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
        self._holiday_source = holiday_source
        self._holiday_years_warmed: set[int] = set()
        self._holiday_years_provisional: set[int] = set()

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
        now = dt_util.utcnow()
        await self._async_warm_holiday_cache(now)
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
        return api_data

    async def _async_warm_holiday_cache(self, now: datetime) -> None:
        """Warm aiopvpc holiday cache off the event loop for csv source."""
        if self._holiday_source != "csv":
            return
        local_date = dt_util.as_local(now).date()
        local_year = local_date.year
        if local_year in self._holiday_years_warmed:
            return
        if local_year in self._holiday_years_provisional:
            await self.hass.async_add_executor_job(_clear_aiopvpc_holiday_cache)

        try:
            await self.hass.async_add_executor_job(
                _warm_aiopvpc_holidays, local_year, self._holiday_source
            )
            self._holiday_years_warmed.add(local_year)
            self._holiday_years_provisional.discard(local_year)
            return
        except Exception:  # noqa: BLE001
            # Jan 1..6: keep retrying current-year fetch while preserving known
            # holiday behavior for Jan 1 / Jan 6 in a provisional cache.
            if local_date.month != 1 or local_date.day > 6:
                raise

        provisional_holidays = _provisional_january_holidays(local_year)
        await self.hass.async_add_executor_job(
            _prime_aiopvpc_holiday_cache,
            local_year,
            self._holiday_source,
            provisional_holidays,
        )
        self._holiday_years_provisional.add(local_year)
