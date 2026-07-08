"""
Simple aio library to download Spanish electricity hourly prices.

* URL for JSON daily files
* Parser for the contents of the JSON files
"""

import logging
from collections.abc import Iterable
from datetime import datetime, timedelta
from itertools import groupby
from operator import itemgetter
from typing import Any

from .const import (
    DataSource,
    EsiosResponse,
    GEOZONE_CANARIAS,
    GEOZONE_CEUTA,
    GEOZONE_ESPANA,
    GEOZONE_ID2NAME,
    GEOZONE_PENINSULA,
    KEY_PVPC,
    PRICE_PRECISION,
    REFERENCE_TZ,
    SENSOR_KEY_TO_DATAID,
    TARIFF2ID,
    TARIFFS,
    URL_ESIOS_TOKEN_RESOURCE,
    URL_PUBLIC_PVPC_RESOURCE,
    UTC_TZ,
    zoneinfo,
)

_LOGGER = logging.getLogger(__name__)

# Local timezones of the geographic zones recognized for the
# "2.0TD Península / Baleares / Canarias" tariff. Baleares shares
# Europe/Madrid with the peninsula; Ceuta/Melilla have their own tariff
# and always map to the Ceuta zone.
_TZ_TO_GEOZONE: dict[str, str] = {
    "Europe/Madrid": GEOZONE_PENINSULA,
    "Atlantic/Canary": GEOZONE_CANARIAS,
}


def _timezone_offset(tz: zoneinfo.ZoneInfo = REFERENCE_TZ) -> timedelta:
    """Fixed offset from Europe/Madrid to the given local timezone.

    Computed at a single reference date, so it is only correct for zones
    whose offset to Madrid never changes (true for all Spanish zones,
    which switch DST on the same dates).
    """
    ref_ts = datetime(2021, 1, 1, tzinfo=REFERENCE_TZ).astimezone(UTC_TZ)
    loc_ts = datetime(2021, 1, 1, tzinfo=tz).astimezone(UTC_TZ)
    return loc_ts - ref_ts


def _select_geo_zone(tariff: str, tz: zoneinfo.ZoneInfo) -> str:
    """Return the ESIOS geo zone for a tariff + local timezone.

    The Ceuta/Melilla tariff always uses the Ceuta zone. For the peninsula
    tariff the recognized Spanish timezones select the zone:
    Europe/Madrid -> Península (shared by Baleares) and
    Atlantic/Canary -> Canarias. Any other timezone defaults to Península
    with a warning: PVPC values are national across the PCB zones, and the
    local-time offset is applied separately by `_timezone_offset`.
    """
    if tariff != TARIFFS[0]:
        return GEOZONE_CEUTA
    geo_zone = _TZ_TO_GEOZONE.get(str(tz))
    if geo_zone is None:
        _LOGGER.warning(
            "Timezone '%s' is not a recognized Spanish zone; assuming %s",
            tz,
            GEOZONE_PENINSULA,
        )
        return GEOZONE_PENINSULA
    return geo_zone


def extract_prices_from_esios_public(
    data: dict[str, Any], key: str, tz: zoneinfo.ZoneInfo = REFERENCE_TZ
) -> EsiosResponse:
    """Parse the contents of a daily PVPC json file."""
    ts_init = (
        datetime.strptime(data["PVPC"][0]["Dia"], "%d/%m/%Y")
        .replace(tzinfo=tz)
        .astimezone(UTC_TZ)
    )

    def _parse_tariff_val(value, prec=PRICE_PRECISION) -> float:
        return round(float(value.replace(",", ".")) / 1000.0, prec)

    pvpc_prices = {
        ts_init + timedelta(hours=i): _parse_tariff_val(values_hour[key])
        for i, values_hour in enumerate(data["PVPC"])
    }

    return EsiosResponse(
        name="PVPC ESIOS",
        data_id="legacy",
        last_update=datetime.now(UTC_TZ).replace(microsecond=0),
        unit="€/kWh",
        series={KEY_PVPC: pvpc_prices},
    )


def extract_prices_from_esios_token(
    data: dict[str, Any],
    sensor_key: str,
    geo_zone: str,
    tz: zoneinfo.ZoneInfo = REFERENCE_TZ,
) -> EsiosResponse:
    """Parse the contents of an 'indicator' json file from ESIOS API."""
    offset_timezone = _timezone_offset(tz)
    indicator_data = data.pop("indicator")
    unit = "•".join(mag["name"] for mag in indicator_data["magnitud"])
    unit_tiempo = "•".join(mag["name"] for mag in indicator_data["tiempo"])
    unit += f"/{unit_tiempo}"
    ts_update = datetime.now(UTC_TZ).replace(microsecond=0)

    def _parse_dt(ts: str) -> datetime:
        return datetime.fromisoformat(ts).astimezone(UTC_TZ) + offset_timezone

    def _value_unit_conversion(value: float) -> float:
        # from €/MWh to €/kWh
        return round(float(value) / 1000.0, PRICE_PRECISION)

    value_gen = groupby(
        sorted(indicator_data["values"], key=itemgetter("geo_id")),
        itemgetter("geo_id"),
    )
    # sort each series by timestamp: downstream consumers rely on
    # chronological iteration order of the price dicts
    parsed_data = {
        GEOZONE_ID2NAME[key]: dict(
            sorted(
                (_parse_dt(item["datetime"]), _value_unit_conversion(item["value"]))
                for item in group
            )
        )
        for key, group in value_gen
    }
    if geo_zone in parsed_data:
        geo_data = parsed_data[geo_zone]
    elif GEOZONE_PENINSULA in parsed_data:
        geo_data = parsed_data[GEOZONE_PENINSULA]
    else:
        geo_data = parsed_data[GEOZONE_ESPANA]

    return EsiosResponse(
        name=indicator_data["name"],
        data_id=str(indicator_data["id"]),
        last_update=ts_update,
        unit=unit,
        series={sensor_key: geo_data},
    )


def extract_esios_data(
    data: dict[str, Any],
    url: str,
    sensor_key: str,
    tariff: str,
    tz: zoneinfo.ZoneInfo = REFERENCE_TZ,
) -> EsiosResponse:
    """Parse the contents of a daily PVPC json file."""
    if url.startswith("https://api.esios.ree.es/archives"):
        return extract_prices_from_esios_public(data, TARIFF2ID[tariff], tz)

    if url.startswith("https://api.esios.ree.es/indicators"):
        geo_zone = _select_geo_zone(tariff, tz)
        return extract_prices_from_esios_token(data, sensor_key, geo_zone, tz)
    raise NotImplementedError(f"Data source not known: {url} >{data}")


def get_daily_urls_to_download(
    source: DataSource,
    sensor_keys: Iterable[str],
    now_local_ref: datetime,
    next_day_local_ref: datetime,
) -> tuple[list[str], list[str]]:
    """Make URLs for ESIOS price series."""
    sensor_keys = list(sensor_keys)
    if source == "esios_public":
        if set(sensor_keys) != {KEY_PVPC}:
            raise ValueError(f"Public API only supports {KEY_PVPC}, got: {sensor_keys}")
        return (
            [URL_PUBLIC_PVPC_RESOURCE.format(day=now_local_ref.date())],
            [URL_PUBLIC_PVPC_RESOURCE.format(day=next_day_local_ref.date())],
        )

    if source != "esios":
        raise ValueError(f"Unknown data source: {source}")
    today = [
        URL_ESIOS_TOKEN_RESOURCE.format(
            ind=SENSOR_KEY_TO_DATAID[key], day=now_local_ref.date()
        )
        for key in sensor_keys
    ]
    tomorrow = [
        URL_ESIOS_TOKEN_RESOURCE.format(
            ind=SENSOR_KEY_TO_DATAID[key], day=next_day_local_ref.date()
        )
        for key in sensor_keys
    ]
    return today, tomorrow
