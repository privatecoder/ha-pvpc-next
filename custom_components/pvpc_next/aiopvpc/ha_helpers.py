"""Home Assistant helper methods."""
# pylint: disable=duplicate-code

from .const import (
    ALL_SENSORS,
    KEY_ADJUSTMENT,
    KEY_INDEXED,
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
    **{f"{tariff}_{KEY_ADJUSTMENT}": KEY_ADJUSTMENT for tariff in _TARIFF_IDS},
    **{f"{tariff}_{KEY_INDEXED}": KEY_INDEXED for tariff in _TARIFF_IDS},
}


def get_enabled_sensor_keys(
    using_private_api: bool, disabled_sensor_ids: list[str]
) -> set[str]:
    """(HA) Get enabled API indicators."""
    sensor_keys = set(ALL_SENSORS) if using_private_api else {KEY_PVPC}
    for unique_id in disabled_sensor_ids:
        disabled_ind = _ha_uniqueid_to_sensor_key.get(unique_id)
        if disabled_ind in sensor_keys:
            sensor_keys.remove(disabled_ind)

    return sensor_keys


def make_sensor_unique_id(config_entry_id: str, sensor_key: str) -> str:
    """(HA) Generate unique_id for each sensor kind and config entry."""
    assert sensor_key in ALL_SENSORS or sensor_key == KEY_INDEXED
    if sensor_key == KEY_PVPC:
        # for old compatibility
        return config_entry_id
    return f"{config_entry_id}_{sensor_key}"
