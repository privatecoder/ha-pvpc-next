"""ESIOS API handler for HomeAssistant. PVPC tariff periods."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache

from holidays.countries.spain import Spain

_PRICE_HOURS_P1_PCB = (10, 11, 12, 13, 18, 19, 20, 21)
_PRICE_HOURS_P2_PCB = (8, 9, 14, 15, 16, 17, 22, 23)
_PRICE_HOURS_P1_CYM = (11, 12, 13, 14, 19, 20, 21, 22)
_PRICE_HOURS_P2_CYM = (8, 9, 10, 15, 16, 17, 18, 23)


@lru_cache(maxsize=32)
def _national_p3_holidays(year: int) -> set[date]:
    national = Spain(years=year, observed=False)
    return set(national.keys())


def _price_period_key(local_ts: datetime, zone_ceuta_melilla: bool) -> str:
    """Return price period key (P1/P2/P3) for current hour."""
    day = local_ts.date()
    national_holiday = day in _national_p3_holidays(day.year)
    if national_holiday or day.isoweekday() >= 6:
        return "P3"
    if local_ts.hour < 8:
        return "P3"
    if zone_ceuta_melilla and local_ts.hour in _PRICE_HOURS_P2_CYM:
        return "P2"
    if not zone_ceuta_melilla and local_ts.hour in _PRICE_HOURS_P2_PCB:
        return "P2"
    if zone_ceuta_melilla and local_ts.hour in _PRICE_HOURS_P1_CYM:
        return "P1"
    if not zone_ceuta_melilla and local_ts.hour in _PRICE_HOURS_P1_PCB:
        return "P1"
    return "P2"


def _power_period_key(local_ts: datetime, _zone_ceuta_melilla: bool) -> str:
    """Return power period key (P1/P3) for current hour."""
    day = local_ts.date()
    national_holiday = day in _national_p3_holidays(day.year)
    if national_holiday or day.isoweekday() >= 6:
        return "P3"
    if local_ts.hour < 8:
        return "P3"
    return "P1"


def get_current_and_next_price_periods(
    local_ts: datetime, zone_ceuta_melilla: bool
) -> tuple[str, str, timedelta]:
    """Get price periods for PVPC 2.0TD."""
    current_period = _price_period_key(local_ts, zone_ceuta_melilla)
    delta = timedelta(hours=1)
    while (
        next_period := _price_period_key(local_ts + delta, zone_ceuta_melilla)
    ) == current_period:
        delta += timedelta(hours=1)
    return current_period, next_period, delta


def get_current_and_next_power_periods(
    local_ts: datetime, zone_ceuta_melilla: bool
) -> tuple[str, str, timedelta]:
    """Get power periods for PVPC 2.0TD."""
    current_period = _power_period_key(local_ts, zone_ceuta_melilla)
    delta = timedelta(hours=1)
    while (
        next_period := _power_period_key(local_ts + delta, zone_ceuta_melilla)
    ) == current_period:
        delta += timedelta(hours=1)
    return current_period, next_period, delta


def get_current_and_next_tariff_periods(
    local_ts: datetime, zone_ceuta_melilla: bool
) -> tuple[str, str, timedelta]:
    """Backward compatible price-periods helper."""
    return get_current_and_next_price_periods(local_ts, zone_ceuta_melilla)
