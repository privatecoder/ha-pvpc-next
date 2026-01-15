"""The PVPC Next integration to collect Spain official electric prices."""

from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .aiopvpc.const import TARIFF_ALIASES, normalize_tariff
from .coordinator import ElecPricesDataUpdateCoordinator, PVPCConfigEntry
from .helpers import get_enabled_sensor_keys
from .const import (
    ATTR_ENABLE_PRIVATE_API,
    ATTR_POWER_P1,
    ATTR_POWER_P2_P3,
    ATTR_TARIFF,
    DEFAULT_ENABLE_PRIVATE_API,
    LEGACY_ATTR_ENABLE_INJECTION_PRICE,
    LEGACY_ATTR_POWER,
    LEGACY_ATTR_POWER_P3,
)

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
    sensor_keys = get_enabled_sensor_keys(
        using_private_api=use_private_api,
        entries=er.async_entries_for_config_entry(entity_registry, entry.entry_id),
        enable_private_api=enable_private_api,
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
    if entry.version >= 4:
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

        if LEGACY_ATTR_POWER_P3 in store:
            if ATTR_POWER_P2_P3 not in store:
                store[ATTR_POWER_P2_P3] = store[LEGACY_ATTR_POWER_P3]
            store.pop(LEGACY_ATTR_POWER_P3, None)
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
            if new_unique_id != entity.unique_id:
                entity_registry.async_update_entity(
                    entity.entity_id, new_unique_id=new_unique_id
                )

    hass.config_entries.async_update_entry(
        entry,
        data=data if migrated else None,
        options=options if migrated else None,
        unique_id=updated_unique_id if updated_unique_id != unique_id else None,
        version=4,
    )
    return True
