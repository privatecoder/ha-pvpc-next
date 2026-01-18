"""The PVPC Next integration to collect Spain official electric prices."""

import logging

from homeassistant.const import CONF_API_TOKEN, CONF_NAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .aiopvpc.const import TARIFF_ALIASES, normalize_tariff
from .coordinator import ElecPricesDataUpdateCoordinator, PVPCConfigEntry
from .helpers import get_enabled_sensor_keys
from .const import (
    ATTR_BETTER_PRICE_TARGET,
    ATTR_ENABLE_PRIVATE_API,
    ATTR_POWER_P1,
    ATTR_POWER_P3,
    ATTR_TARIFF,
    DEFAULT_ENABLE_PRIVATE_API,
    LEGACY_ATTR_ENABLE_INJECTION_PRICE,
    LEGACY_ATTR_POWER,
    LEGACY_ATTR_POWER_P2_P3,
    LEGACY_ATTR_POWER_P3,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PVPCConfigEntry) -> bool:
    """Set up pvpc hourly pricing from a config entry."""
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
    sensor_keys = get_enabled_sensor_keys(
        using_private_api=use_private_api,
        entries=er.async_entries_for_config_entry(entity_registry, entry.entry_id),
        enable_private_api=enable_private_api,
    )
    _LOGGER.debug(
        "PVPC Next config entry_id=%s unique_id=%s name=%s tariff=%s timezone=%s "
        "power_p1=%s power_p3=%s better_price_target=%s enable_private_api=%s "
        "use_private_api=%s api_token_set=%s sensor_keys=%s entry_version=%s",
        entry.entry_id,
        entry.unique_id,
        config.get(CONF_NAME),
        config.get(ATTR_TARIFF),
        hass.config.time_zone,
        power_p1,
        power_p3,
        better_price_target,
        enable_private_api,
        use_private_api,
        bool(api_token),
        sorted(sensor_keys),
        entry.version,
    )
    coordinator = ElecPricesDataUpdateCoordinator(
        hass, entry, sensor_keys, use_private_api
    )
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PVPCConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: PVPCConfigEntry) -> bool:
    """Migrate old config entries to the current schema."""
    if entry.version >= 6:
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
        version=6,
    )
    return True
