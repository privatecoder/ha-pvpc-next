"""Helper functions to relate sensors keys and unique ids."""

from homeassistant.helpers.entity_registry import RegistryEntry

from .aiopvpc.const import (
    ALL_SENSORS,
    KEY_INJECTION,
    KEY_MAG,
    KEY_OMIE,
    KEY_PVPC,
    LEGACY_TARIFFS,
    TARIFFS,
)

_TARIFF_IDS = (*TARIFFS, *LEGACY_TARIFFS)
_ha_uniqueid_to_sensor_key = {
    **{tariff: KEY_PVPC for tariff in _TARIFF_IDS},
    **{f"{tariff}_{KEY_INJECTION}": KEY_INJECTION for tariff in _TARIFF_IDS},
    **{f"{tariff}_INYECTION": KEY_INJECTION for tariff in _TARIFF_IDS},
    **{f"{tariff}_{KEY_MAG}": KEY_MAG for tariff in _TARIFF_IDS},
    **{f"{tariff}_{KEY_OMIE}": KEY_OMIE for tariff in _TARIFF_IDS},
}


def get_enabled_sensor_keys(
    using_private_api: bool, entries: list[RegistryEntry]
) -> set[str]:
    """Get enabled API indicators."""
    if not using_private_api:
        return {KEY_PVPC}
    if len(entries) > 1:
        # activate only enabled sensors
        sensor_keys: set[str] = set()
        for sensor in entries:
            if sensor.disabled:
                continue
            sensor_key = _ha_uniqueid_to_sensor_key.get(sensor.unique_id)
            if sensor_key is not None:
                sensor_keys.add(sensor_key)
        return sensor_keys
    # default sensors when enabling token access
    return {KEY_PVPC, KEY_INJECTION}


def make_sensor_unique_id(config_entry_id: str | None, sensor_key: str) -> str:
    """Generate unique_id for each sensor kind and config entry."""
    assert sensor_key in ALL_SENSORS
    assert config_entry_id is not None
    if sensor_key == KEY_PVPC:
        # for old compatibility
        return config_entry_id
    return f"{config_entry_id}_{sensor_key}"
