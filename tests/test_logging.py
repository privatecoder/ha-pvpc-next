"""Tests for PVPC Next logging behavior."""

import logging

from custom_components.pvpc_next import _sync_dependency_log_levels


def test_sync_dependency_log_levels_propagates_debug() -> None:
    """Debug on integration should enable dependency debug logs."""
    integration_logger = logging.getLogger("custom_components.pvpc_next")
    aiopvpc_logger = logging.getLogger("custom_components.pvpc_next.aiopvpc")
    pvpc_holidays_logger = logging.getLogger("custom_components.pvpc_next.pvpc_holidays")
    original_levels = (
        integration_logger.level,
        aiopvpc_logger.level,
        pvpc_holidays_logger.level,
    )

    try:
        integration_logger.setLevel(logging.DEBUG)
        aiopvpc_logger.setLevel(logging.WARNING)
        pvpc_holidays_logger.setLevel(logging.NOTSET)

        _sync_dependency_log_levels()

        assert aiopvpc_logger.level == logging.DEBUG
        assert pvpc_holidays_logger.level == logging.DEBUG
    finally:
        integration_logger.setLevel(original_levels[0])
        aiopvpc_logger.setLevel(original_levels[1])
        pvpc_holidays_logger.setLevel(original_levels[2])


def test_sync_dependency_log_levels_keeps_more_verbose_dependency_level() -> None:
    """Do not reduce explicit dependency debug level."""
    integration_logger = logging.getLogger("custom_components.pvpc_next")
    aiopvpc_logger = logging.getLogger("custom_components.pvpc_next.aiopvpc")
    original_levels = (integration_logger.level, aiopvpc_logger.level)

    try:
        integration_logger.setLevel(logging.INFO)
        aiopvpc_logger.setLevel(logging.DEBUG)

        _sync_dependency_log_levels()

        assert aiopvpc_logger.level == logging.DEBUG
    finally:
        integration_logger.setLevel(original_levels[0])
        aiopvpc_logger.setLevel(original_levels[1])
