"""The PVPC Next integration to collect Spain official electric prices."""

from homeassistant.const import CONF_API_TOKEN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .aiopvpc.const import TARIFF_ALIASES, normalize_tariff
from .coordinator import ElecPricesDataUpdateCoordinator, PVPCConfigEntry
from .helpers import get_enabled_sensor_keys
from .const import (
    ATTR_ENABLE_INJECTION_PRICE,
    ATTR_POWER_P1,
    ATTR_POWER_P2_P3,
    ATTR_TARIFF,
    DEFAULT_ENABLE_INJECTION_PRICE,
    LEGACY_ATTR_POWER,
    LEGACY_ATTR_POWER_P3,
)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: PVPCConfigEntry) -> bool:
    """Set up pvpc hourly pricing from a config entry."""
    entity_registry = er.async_get(hass)
    config = {**entry.data, **entry.options}
    api_token = config.get(CONF_API_TOKEN)
    enable_injection_price = config.get(ATTR_ENABLE_INJECTION_PRICE)
    if enable_injection_price is None:
        enable_injection_price = (
            bool(api_token) if api_token else DEFAULT_ENABLE_INJECTION_PRICE
        )
    sensor_keys = get_enabled_sensor_keys(
        using_private_api=api_token is not None,
        entries=er.async_entries_for_config_entry(entity_registry, entry.entry_id),
        enable_injection_price=enable_injection_price,
    )
    coordinator = ElecPricesDataUpdateCoordinator(hass, entry, sensor_keys)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: PVPCConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, entry: PVPCConfigEntry) -> bool:
    """Migrate old config entries to the current schema."""
    if entry.version >= 3:
        return True

    data = {**entry.data}
    options = {**entry.options}
    migrated = False

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
    unique_id = entry.unique_id
    updated_unique_id = TARIFF_ALIASES.get(unique_id, unique_id)
    if updated_unique_id != unique_id:
        migrated = True

    hass.config_entries.async_update_entry(
        entry,
        data=data if migrated else None,
        options=options if migrated else None,
        unique_id=updated_unique_id if updated_unique_id != unique_id else None,
        version=3,
    )
    return True
