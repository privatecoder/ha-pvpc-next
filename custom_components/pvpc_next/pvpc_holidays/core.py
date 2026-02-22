"""PVPC holiday logic for Spain (Peaje 2.0TD P3/valle)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
import csv
import io
import logging
from typing import Literal
import unicodedata
from urllib.error import URLError
from urllib.request import Request, urlopen

DEFAULT_CSV_URL = (
    "https://www.seg-social.es/wps/PA_POINCALAB/CalendarioServlet"
    "?exportacion=CSV&tipo=2"
)

FIXED_HOLIDAYS: tuple[tuple[int, int, str], ...] = (
    (11, 1, "Todos los Santos"),
    (12, 6, "Día de la Constitución"),
)
NEXT_YEAR_FIXED_HOLIDAYS: tuple[tuple[int, int, str], ...] = (
    (1, 1, "Año Nuevo"),
    (1, 6, "Epifanía del Señor"),
)

HolidaySource = Literal["csv", "python-holidays"]

_CANONICAL_NAME_MAP = {
    "ano nuevo": "Año Nuevo",
    "epifania del senor": "Epifanía del Señor",
    "viernes santo": "Viernes Santo",
    "fiesta del trabajo": "Fiesta del Trabajo",
    "asuncion de la virgen": "Asunción de la Virgen",
    "fiesta nacional de espana": "Fiesta Nacional de España",
    "todos los santos": "Todos los Santos",
    "dia de la constitucion": "Día de la Constitución",
    "dia de la constitucion espanola": "Día de la Constitución",
    "inmaculada concepcion": "Inmaculada Concepción",
    "natividad del senor": "Natividad del Señor",
}

_WEEKDAY_NAMES = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


class PVPCError(RuntimeError):
    """Base class for PVPC-specific errors."""


@dataclass(frozen=True, slots=True)
class HolidayRecord:
    """Single holiday entry used across source loading and filtering."""

    day: date
    description: str
    holiday_type: str
    province: str
    locality: str


def _log_or_default(logger: logging.Logger | None) -> logging.Logger:
    return logger or logging.getLogger(__name__)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(ascii_only.lower().split())


def _weekday_short(day: date) -> str:
    return _WEEKDAY_NAMES[day.weekday()]


def _is_weekend(day: date) -> bool:
    return day.weekday() >= 5


def _canonicalize_holiday_name(name: str) -> str:
    normalized_name = _normalize(name)
    return _CANONICAL_NAME_MAP.get(normalized_name, " ".join(name.split()))


def _resolve_url(url: str, year: int) -> str:
    if "{year}" in url:
        return url.format(year=year)
    return url


def download_holiday_csv(
    year: int,
    *,
    csv_url: str = DEFAULT_CSV_URL,
    timeout: int = 20,
    logger: logging.Logger | None = None,
) -> str:
    """Download the holiday CSV feed."""
    log = _log_or_default(logger)
    resolved_url = _resolve_url(csv_url, year)
    request = Request(
        resolved_url,
        headers={
            "User-Agent": "spanish-pvpc-holidays/0.1",
            "Accept": "text/csv,*/*;q=0.8",
        },
    )

    log.debug("Downloading holiday CSV: %s", resolved_url)
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = response.read()
            charset = response.headers.get_content_charset()
    except URLError as exc:
        log.exception("CSV download failed.")
        raise PVPCError("CSV download failed") from exc

    content = _decode_payload(payload, charset)
    log.debug("CSV downloaded (%d characters)", len(content))
    return content


def _decode_payload(payload: bytes, header_charset: str | None) -> str:
    encodings: list[str] = []
    if header_charset:
        encodings.append(header_charset)
    encodings.extend(["utf-8-sig", "latin-1"])

    for encoding in encodings:
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue

    # Final fallback for robust error visibility
    return payload.decode("utf-8", errors="replace")


def parse_holiday_csv(
    csv_text: str, *, logger: logging.Logger | None = None
) -> list[HolidayRecord]:
    """Parse CSV text into HolidayRecord entries."""
    log = _log_or_default(logger)
    records: list[HolidayRecord] = []

    reader = csv.DictReader(io.StringIO(csv_text))
    required = {"FECHA", "DESCRIPCION", "TIPO", "PROVINCIA", "LOCALIDAD"}
    missing = required.difference(reader.fieldnames or [])
    if missing:
        message = f"CSV header is incomplete, missing: {sorted(missing)}"
        log.error(message)
        raise PVPCError(message)

    for line_no, row in enumerate(reader, start=2):
        raw_date = (row.get("FECHA") or "").strip()
        source_description = (row.get("DESCRIPCION") or "").strip()

        if not raw_date or not source_description:
            log.error(
                "Line %d discarded: FECHA or DESCRIPCION is missing (FECHA=%r, DESCRIPCION=%r)",
                line_no,
                raw_date,
                source_description,
            )
            continue

        try:
            parsed_day = datetime.strptime(raw_date, "%d-%m-%Y").date()
        except ValueError:
            log.error("Line %d discarded: invalid date format %r", line_no, raw_date)
            continue

        record = HolidayRecord(
            day=parsed_day,
            description=_canonicalize_holiday_name(source_description),
            holiday_type=(row.get("TIPO") or "").strip(),
            province=(row.get("PROVINCIA") or "").strip(),
            locality=(row.get("LOCALIDAD") or "").strip(),
        )
        records.append(record)
        message = "CSV holiday found: %s (%s) | tipo=%s | province=%s | locality=%s"
        if record.description != source_description:
            message += " | mapped_from=%s"
            log.debug(
                message,
                record.day.isoformat(),
                record.description,
                record.holiday_type or "-",
                record.province or "-",
                record.locality or "-",
                source_description,
            )
            continue
        log.debug(
            message,
            record.day.isoformat(),
            record.description,
            record.holiday_type or "-",
            record.province or "-",
            record.locality or "-",
        )

    if not records:
        log.error("No valid holidays found in CSV.")
        raise PVPCError("No valid holidays found in CSV")

    return records


def fetch_python_holidays(
    year: int,
    *,
    logger: logging.Logger | None = None,
) -> list[HolidayRecord]:
    """Load Spain national holidays for one year from python-holidays."""
    log = _log_or_default(logger)
    try:
        import holidays  # type: ignore[import-not-found]  # pylint: disable=import-outside-toplevel
    except ModuleNotFoundError as exc:
        raise PVPCError(
            "python-holidays source requested but dependency is missing. "
            "Install optional dependency 'holidays' first."
        ) from exc

    calendar = holidays.country_holidays("ES", years=[year])
    records: list[HolidayRecord] = []
    for holiday_day, source_description in sorted(calendar.items()):
        description = _canonicalize_holiday_name(str(source_description))
        record = HolidayRecord(
            day=holiday_day,
            description=description,
            holiday_type="Nacional",
            province="",
            locality="",
        )
        records.append(record)
        message = "python-holidays holiday found: %s (%s)"
        if description != str(source_description):
            message += " | mapped_from=%s"
            log.debug(message, holiday_day.isoformat(), description, source_description)
            continue
        log.debug(message, holiday_day.isoformat(), description)

    if not records:
        raise PVPCError(f"No holidays found from python-holidays for year {year}")
    return records


def load_holiday_records(  # pylint: disable=too-many-arguments
    year: int,
    *,
    source: HolidaySource = "csv",
    csv_url: str = DEFAULT_CSV_URL,
    timeout: int = 20,
    logger: logging.Logger | None = None,
    warmup: bool = False,
) -> list[HolidayRecord]:
    """Load holiday records from the selected source."""
    log = _log_or_default(logger)
    mode = "warmup" if warmup else "full"
    log.info("Holiday source selected: %s | year=%d | mode=%s", source, year, mode)
    if source == "csv":
        csv_text = download_holiday_csv(year, csv_url=csv_url, timeout=timeout, logger=log)
        records = parse_holiday_csv(csv_text, logger=log)
    elif source == "python-holidays":
        records = fetch_python_holidays(year, logger=log)
    else:
        raise PVPCError(f"Unsupported source: {source!r}")

    log.debug(
        "Loaded %d records from source=%s for year=%d | mode=%s",
        len(records),
        source,
        year,
        mode,
    )
    return records


async def async_load_holiday_records(  # pylint: disable=too-many-arguments
    year: int,
    *,
    source: HolidaySource = "csv",
    csv_url: str = DEFAULT_CSV_URL,
    timeout: int = 20,
    logger: logging.Logger | None = None,
    warmup: bool = False,
) -> list[HolidayRecord]:
    """Async-safe wrapper for load_holiday_records, executed in a worker thread."""
    return await asyncio.to_thread(
        load_holiday_records,
        year,
        source=source,
        csv_url=csv_url,
        timeout=timeout,
        logger=logger,
        warmup=warmup,
    )


def warmup_source(
    year: int,
    *,
    source: HolidaySource = "csv",
    csv_url: str = DEFAULT_CSV_URL,
    timeout: int = 20,
    logger: logging.Logger | None = None,
) -> int:
    """Warm up selected source (import/metadata/dataset loading) and return loaded record count."""
    log = _log_or_default(logger)
    records = load_holiday_records(
        year,
        source=source,
        csv_url=csv_url,
        timeout=timeout,
        logger=log,
        warmup=True,
    )
    count = len(records)
    log.info(
        "Warmup completed for source=%s | year=%d | warmup=%s | record_count=%d",
        source,
        year,
        True,
        count,
    )
    return count


async def async_warmup_source(
    year: int,
    *,
    source: HolidaySource = "csv",
    csv_url: str = DEFAULT_CSV_URL,
    timeout: int = 20,
    logger: logging.Logger | None = None,
) -> int:
    """Async-safe warmup helper, executed in a worker thread."""
    return await asyncio.to_thread(
        warmup_source,
        year,
        source=source,
        csv_url=csv_url,
        timeout=timeout,
        logger=logger,
    )


def select_pvpc_holidays(
    records: Iterable[HolidayRecord],
    *,
    year: int,
    logger: logging.Logger | None = None,
) -> dict[date, str]:
    """Apply PVPC rules to parsed holidays."""
    log = _log_or_default(logger)
    selected: dict[date, str] = {}
    next_year = year + 1

    for record in sorted(records, key=lambda item: (item.day, item.description)):
        if record.day.year != year:
            log.debug(
                "EXCLUDE %s (%s): different year (%d instead of %d)",
                record.day.isoformat(),
                record.description,
                record.day.year,
                year,
            )
            continue

        if _is_weekend(record.day):
            log.debug(
                "EXCLUDE %s (%s): weekend (%s)",
                record.day.isoformat(),
                record.description,
                _weekday_short(record.day),
            )
            continue

        if _normalize(record.description) == "viernes santo":
            log.debug(
                "EXCLUDE %s (%s): Viernes Santo explicitly excluded (not a fixed date)",
                record.day.isoformat(),
                record.description,
            )
            continue

        if record.day in selected:
            log.debug(
                "EXCLUDE %s (%s): duplicate, date already present as %s",
                record.day.isoformat(),
                record.description,
                selected[record.day],
            )
            continue

        selected[record.day] = record.description
        log.debug("INCLUDE %s (%s)", record.day.isoformat(), record.description)

    for month, day_of_month, description in FIXED_HOLIDAYS:
        fixed_day = date(year, month, day_of_month)
        if _is_weekend(fixed_day):
            log.debug(
                "EXCLUDE %s (%s): fixed date falls on weekend (%s)",
                fixed_day.isoformat(),
                description,
                _weekday_short(fixed_day),
            )
            continue

        if fixed_day in selected:
            log.debug("KEEP %s (%s): already present", fixed_day.isoformat(), selected[fixed_day])
            continue

        selected[fixed_day] = description
        log.debug("INCLUDE %s (%s): fixed date added", fixed_day.isoformat(), description)

    for month, day_of_month, description in NEXT_YEAR_FIXED_HOLIDAYS:
        fixed_day = date(next_year, month, day_of_month)
        if _is_weekend(fixed_day):
            log.debug(
                "EXCLUDE %s (%s): next-year fixed date falls on weekend (%s)",
                fixed_day.isoformat(),
                description,
                _weekday_short(fixed_day),
            )
            continue
        if fixed_day in selected:
            log.debug(
                "KEEP %s (%s): next-year fixed date already present",
                fixed_day.isoformat(),
                selected[fixed_day],
            )
            continue
        selected[fixed_day] = description
        log.debug("INCLUDE %s (%s): next-year fixed date added", fixed_day.isoformat(), description)

    final_sorted = dict(sorted(selected.items(), key=lambda item: item[0]))
    log.debug("Final PVPC holiday list for %d/%d (%d entries):", year, next_year, len(final_sorted))
    for holiday_day, description in final_sorted.items():
        log.debug("  %s - %s", holiday_day.isoformat(), description)

    return final_sorted


def get_pvpc_holidays(
    year: int,
    *,
    source: HolidaySource = "csv",
    csv_url: str = DEFAULT_CSV_URL,
    timeout: int = 20,
    logger: logging.Logger | None = None,
) -> dict[date, str]:
    """Load holidays from selected source, apply PVPC rules, and append next-year 01.01/06.01."""
    log = _log_or_default(logger)
    records = load_holiday_records(
        year,
        source=source,
        csv_url=csv_url,
        timeout=timeout,
        logger=log,
    )
    result = select_pvpc_holidays(records, year=year, logger=log)
    log.info(
        "Computed PVPC holidays for %d/%d from source=%s | warmup=%s | final_count=%d",
        year,
        year + 1,
        source,
        False,
        len(result),
    )
    return result


async def async_get_pvpc_holidays(
    year: int,
    *,
    source: HolidaySource = "csv",
    csv_url: str = DEFAULT_CSV_URL,
    timeout: int = 20,
    logger: logging.Logger | None = None,
) -> dict[date, str]:
    """Async-safe wrapper for get_pvpc_holidays, executed in a worker thread."""
    return await asyncio.to_thread(
        get_pvpc_holidays,
        year,
        source=source,
        csv_url=csv_url,
        timeout=timeout,
        logger=logger,
    )
