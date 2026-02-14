"""The PVPC Next integration to collect Spain official electric prices."""

import logging

from homeassistant.const import CONF_API_TOKEN, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from aiopvpc.const import KEY_ADJUSTMENT, TARIFF_ALIASES, normalize_tariff
from .coordinator import ElecPricesDataUpdateCoordinator, PVPCConfigEntry
from .helpers import get_enabled_sensor_keys
from .const import (
    ATTR_BETTER_PRICE_TARGET,
    ATTR_ENABLE_PRIVATE_API,
    ATTR_HOLIDAY_SOURCE,
    ATTR_PRICE_MODE,
    ATTR_SHOW_REFERENCE_PRICE,
    ATTR_NEXT_BEST_IN_UPDATE,
    ATTR_NEXT_PERIOD_IN_UPDATE,
    ATTR_NEXT_POWER_PERIOD_IN_UPDATE,
    ATTR_NEXT_PRICE_IN_UPDATE,
    ATTR_POWER_P1,
    ATTR_POWER_P3,
    ATTR_TARIFF,
    DEFAULT_HOLIDAY_SOURCE,
    DEFAULT_PRICE_MODE,
    DEFAULT_SHOW_REFERENCE_PRICE,
    DEFAULT_UPDATE_FREQUENCY,
    DEFAULT_ENABLE_PRIVATE_API,
    LEGACY_ATTR_ENABLE_INJECTION_PRICE,
    LEGACY_ATTR_POWER,
    LEGACY_ATTR_POWER_P2_P3,
    LEGACY_ATTR_POWER_P3,
    normalize_holiday_source,
    normalize_price_mode,
    UPDATE_FREQUENCY_BY_SENSOR,
    UPDATE_FREQUENCY_OPTIONS,
)

_LOGGER = logging.getLogger(__name__)
_DEPENDENCY_LOGGERS: tuple[str, ...] = (
    "aiopvpc",
    "pvpc_holidays",
    "pvpc_holidays.core",
    "pvpc_holidays.csv_source",
    "pvpc_holidays.holidays_source",
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


def _sync_dependency_log_levels() -> None:
    """Align dependency logger levels with integration logger level."""
    integration_level = _LOGGER.getEffectiveLevel()
    for logger_name in _DEPENDENCY_LOGGERS:
        dependency_logger = logging.getLogger(logger_name)
        if (
            dependency_logger.level == logging.NOTSET
            or dependency_logger.level > integration_level
        ):
            dependency_logger.setLevel(integration_level)


async def async_setup_entry(hass: HomeAssistant, entry: PVPCConfigEntry) -> bool:
    """Set up pvpc hourly pricing from a config entry."""
    _sync_dependency_log_levels()
    entity_registry = er.async_get(hass)
    config = {**entry.data, **entry.options}
    api_token = config.get(CONF_API_TOKEN)
    enable_private_api = config.get(ATTR_ENABLE_PRIVATE_API)
    if enable_private_api is None:
        enable_private_api = config.get(LEGACY_ATTR_ENABLE_INJECTION_PRICE)
    if enable_private_api is None:
        enable_private_api = (
            bool(api_token) if api_token else DEFAULT_ENABLE_PRIVATE_API
        )
    use_private_api = bool(api_token) and enable_private_api
    power_p1 = config.get(ATTR_POWER_P1, config.get(LEGACY_ATTR_POWER))
    power_p3 = config.get(
        ATTR_POWER_P3,
        config.get(LEGACY_ATTR_POWER_P2_P3, config.get(LEGACY_ATTR_POWER_P3)),
    )
    better_price_target = config.get(ATTR_BETTER_PRICE_TARGET)
    holiday_source = normalize_holiday_source(
        config.get(ATTR_HOLIDAY_SOURCE, DEFAULT_HOLIDAY_SOURCE)
    )
    next_price_in_update = config.get(
        ATTR_NEXT_PRICE_IN_UPDATE, DEFAULT_UPDATE_FREQUENCY
    )
    next_best_in_update = config.get(
        ATTR_NEXT_BEST_IN_UPDATE, DEFAULT_UPDATE_FREQUENCY
    )
    next_period_in_update = config.get(
        ATTR_NEXT_PERIOD_IN_UPDATE, DEFAULT_UPDATE_FREQUENCY
    )
    next_power_period_in_update = config.get(
        ATTR_NEXT_POWER_PERIOD_IN_UPDATE, DEFAULT_UPDATE_FREQUENCY
    )
    if next_price_in_update not in UPDATE_FREQUENCY_OPTIONS:
        next_price_in_update = DEFAULT_UPDATE_FREQUENCY
    if next_best_in_update not in UPDATE_FREQUENCY_OPTIONS:
        next_best_in_update = DEFAULT_UPDATE_FREQUENCY
    if next_period_in_update not in UPDATE_FREQUENCY_OPTIONS:
        next_period_in_update = DEFAULT_UPDATE_FREQUENCY
    if next_power_period_in_update not in UPDATE_FREQUENCY_OPTIONS:
        next_power_period_in_update = DEFAULT_UPDATE_FREQUENCY
    sensor_keys = get_enabled_sensor_keys(
        using_private_api=use_private_api,
        entries=er.async_entries_for_config_entry(entity_registry, entry.entry_id),
        enable_private_api=enable_private_api,
    )
    price_mode = normalize_price_mode(config.get(ATTR_PRICE_MODE, DEFAULT_PRICE_MODE))
    show_reference_price = config.get(
        ATTR_SHOW_REFERENCE_PRICE, DEFAULT_SHOW_REFERENCE_PRICE
    )
    if use_private_api and (
        price_mode == "indexed" or (price_mode == "pvpc" and show_reference_price)
    ):
        sensor_keys.add(KEY_ADJUSTMENT)
    coordinator = ElecPricesDataUpdateCoordinator(
        hass, entry, sensor_keys, use_private_api
    )
    _LOGGER.debug(
        "PVPC Next config entry_id=%s unique_id=%s name=%s tariff=%s timezone=%s "
        "power_p1=%s power_p3=%s better_price_target=%s holiday_source=%s "
        "price_mode=%s show_reference_price=%s "
        "enable_private_api=%s next_price_in_update=%s next_best_in_update=%s "
        "next_period_in_update=%s next_power_period_in_update=%s "
        "coordinator_update_interval=%s "
        "use_private_api=%s api_token_set=%s sensor_keys=%s entry_version=%s",
        entry.entry_id,
        entry.unique_id,
        config.get(CONF_NAME),
        config.get(ATTR_TARIFF),
        hass.config.time_zone,
        power_p1,
        power_p3,
        better_price_target,
        holiday_source,
        price_mode,
        show_reference_price,
        enable_private_api,
        next_price_in_update,
        next_best_in_update,
        next_period_in_update,
        next_power_period_in_update,
        coordinator.update_interval,
        use_private_api,
        bool(api_token),
        sorted(sensor_keys),
        entry.version,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _apply_update_frequency_disables(entity_registry, entry, config)
    return True


def _apply_update_frequency_disables(
    entity_registry: er.EntityRegistry,
    entry: PVPCConfigEntry,
    config: dict,
) -> None:
    """Disable/enable minute-update sensors based on options."""
    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    if not entity_entries:
        return
    for entity_entry in entity_entries:
        unique_id = entity_entry.unique_id
        if not unique_id:
            continue
        matched = False
        for sensor_key, option_key in UPDATE_FREQUENCY_BY_SENSOR.items():
            if unique_id.endswith(f"_{sensor_key}"):
                matched = True
                frequency = config.get(option_key, DEFAULT_UPDATE_FREQUENCY)
                if frequency not in UPDATE_FREQUENCY_OPTIONS:
                    frequency = DEFAULT_UPDATE_FREQUENCY
                if frequency == "disabled":
                    if (
                        entity_entry.disabled_by
                        != er.RegistryEntryDisabler.INTEGRATION
                    ):
                        entity_registry.async_update_entity(
                            entity_entry.entity_id,
                            disabled_by=er.RegistryEntryDisabler.INTEGRATION,
                        )
                elif (
                    entity_entry.disabled_by
                    == er.RegistryEntryDisabler.INTEGRATION
                ):
                    entity_registry.async_update_entity(
                        entity_entry.entity_id,
                        disabled_by=None,
                    )
                break
        if not matched:
            continue


async def async_unload_entry(hass: HomeAssistant, entry: PVPCConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: PVPCConfigEntry) -> bool:
    """Migrate old config entries to the current schema."""
    if entry.version >= 7:
        return True

    data = {**entry.data}
    options = {**entry.options}
    migrated = False
    entry_unique_id = entry.unique_id

    for store in (data, options):
        tariff = store.get(ATTR_TARIFF)
        if tariff:
            normalized = normalize_tariff(tariff)
            if normalized != tariff:
                store[ATTR_TARIFF] = normalized
                migrated = True

        if LEGACY_ATTR_POWER in store:
            if ATTR_POWER_P1 not in store:
                store[ATTR_POWER_P1] = store[LEGACY_ATTR_POWER]
            store.pop(LEGACY_ATTR_POWER, None)
            migrated = True

        if LEGACY_ATTR_POWER_P2_P3 in store:
            if ATTR_POWER_P3 not in store:
                store[ATTR_POWER_P3] = store[LEGACY_ATTR_POWER_P2_P3]
            store.pop(LEGACY_ATTR_POWER_P2_P3, None)
            migrated = True
        if LEGACY_ATTR_POWER_P3 in store and ATTR_POWER_P3 not in store:
            store[ATTR_POWER_P3] = store[LEGACY_ATTR_POWER_P3]
            migrated = True
        if LEGACY_ATTR_ENABLE_INJECTION_PRICE in store:
            if ATTR_ENABLE_PRIVATE_API not in store:
                store[ATTR_ENABLE_PRIVATE_API] = store[
                    LEGACY_ATTR_ENABLE_INJECTION_PRICE
                ]
            store.pop(LEGACY_ATTR_ENABLE_INJECTION_PRICE, None)
            migrated = True

        if ATTR_HOLIDAY_SOURCE in store:
            holiday_source = store.get(ATTR_HOLIDAY_SOURCE)
            normalized_holiday_source = normalize_holiday_source(holiday_source)
            if holiday_source != normalized_holiday_source:
                store[ATTR_HOLIDAY_SOURCE] = normalized_holiday_source
                migrated = True

    if ATTR_HOLIDAY_SOURCE not in options and ATTR_HOLIDAY_SOURCE not in data:
        data[ATTR_HOLIDAY_SOURCE] = DEFAULT_HOLIDAY_SOURCE
        migrated = True
    unique_id = entry.unique_id
    updated_unique_id = TARIFF_ALIASES.get(unique_id, unique_id)
    if updated_unique_id != unique_id:
        migrated = True
    entity_registry = er.async_get(hass)
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    )
    if entry_unique_id or entity_entries:
        key_migrations = {
            "pvpc_hours_to_next_period": "pvpc_next_period_in",
            "pvpc_next_better_price": "pvpc_next_best_price",
            "pvpc_time_to_better_price": "pvpc_time_to_next_best",
            "pvpc_better_price_level": "pvpc_next_best_price_level",
            "pvpc_power_period": "pvpc_current_power_period",
        }
        for entity in entity_entries:
            new_unique_id = entity.unique_id
            for legacy_tariff, new_tariff in TARIFF_ALIASES.items():
                if new_unique_id == legacy_tariff:
                    new_unique_id = new_tariff
                    break
                if new_unique_id.startswith(f"{legacy_tariff}_"):
                    new_unique_id = f"{new_tariff}{new_unique_id[len(legacy_tariff):]}"
                    break
            if new_unique_id.endswith("_INYECTION"):
                new_unique_id = new_unique_id.replace("_INYECTION", "_INJECTION")
            for old_key, new_key in key_migrations.items():
                suffix = f"_{old_key}"
                if new_unique_id.endswith(suffix):
                    new_unique_id = f"{new_unique_id[: -len(suffix)]}_{new_key}"
                    break
            if new_unique_id != entity.unique_id:
                entity_registry.async_update_entity(
                    entity.entity_id, new_unique_id=new_unique_id
                )
                migrated = True

    hass.config_entries.async_update_entry(
        entry,
        data=data if migrated else None,
        options=options if migrated else None,
        unique_id=updated_unique_id if updated_unique_id != unique_id else None,
        version=7,
    )
    return True
