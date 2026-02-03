"""Tests for PVPC Next."""

# pylint: disable=invalid-name

import pytest

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    _ = enable_custom_integrations
    yield
