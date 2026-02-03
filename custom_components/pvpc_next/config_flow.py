"""Config flow for PVPC Next integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    SOURCE_REAUTH,
    ConfigEntry,
    ConfigFlow,
    OptionsFlowWithReload,
)
from homeassistant.const import CONF_API_TOKEN, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
)
from homeassistant.util import dt as dt_util

from aiopvpc import PVPCData, DEFAULT_POWER_KW
from .const import (
    BETTER_PRICE_TARGETS,
    DOMAIN,
    DEFAULT_NAME,
    DEFAULT_TARIFF,
    DEFAULT_HOLIDAY_SOURCE,
    DEFAULT_UPDATE_FREQUENCY,
    ATTR_POWER_P1,
    ATTR_POWER_P3,
    ATTR_BETTER_PRICE_TARGET,
    ATTR_ENABLE_PRIVATE_API,
    ATTR_HOLIDAY_SOURCE,
    ATTR_NEXT_BEST_IN_UPDATE,
    ATTR_NEXT_PERIOD_IN_UPDATE,
    ATTR_NEXT_POWER_PERIOD_IN_UPDATE,
    ATTR_NEXT_PRICE_IN_UPDATE,
    ATTR_TARIFF,
    LEGACY_ATTR_ENABLE_INJECTION_PRICE,
    LEGACY_ATTR_POWER,
    LEGACY_ATTR_POWER_P2_P3,
    LEGACY_ATTR_POWER_P3,
    DEFAULT_BETTER_PRICE_TARGET,
    DEFAULT_ENABLE_PRIVATE_API,
    HOLIDAY_SOURCES,
    UPDATE_FREQUENCY_OPTIONS,
    VALID_POWER,
    VALID_TARIFF,
    normalize_holiday_source,
)

_MAIL_TO_LINK = (
    "[consultasios@ree.es](mailto:consultasios@ree.es?subject=Personal%20token%20request)"
)


class PVPCOptionsFlowHandler(OptionsFlowWithReload):
    """Handle PVPC options flow."""

    _power_p1: float | None = None
    _power_p3: float | None = None
    _better_price_target: str | None = None
    _enable_private_api: bool | None = None
    _next_price_in_update: str | None = None
    _next_best_in_update: str | None = None
    _next_period_in_update: str | None = None
    _next_power_period_in_update: str | None = None
    _holiday_source: str | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage the options."""
        options = self.config_entry.options
        data = self.config_entry.data

        def _get_power_value(primary_key: str, legacy_key: str) -> float:
            value = options.get(
                primary_key,
                options.get(legacy_key, data.get(primary_key, data.get(legacy_key))),
            )
            return DEFAULT_POWER_KW if value is None else value

        power_p1 = _get_power_value(ATTR_POWER_P1, LEGACY_ATTR_POWER)
        power_p3 = _get_power_value(ATTR_POWER_P3, LEGACY_ATTR_POWER_P2_P3)
        better_price_target = options.get(
            ATTR_BETTER_PRICE_TARGET,
            data.get(ATTR_BETTER_PRICE_TARGET, DEFAULT_BETTER_PRICE_TARGET),
        )
        next_price_in_update = options.get(
            ATTR_NEXT_PRICE_IN_UPDATE,
            data.get(ATTR_NEXT_PRICE_IN_UPDATE, DEFAULT_UPDATE_FREQUENCY),
        )
        next_best_in_update = options.get(
            ATTR_NEXT_BEST_IN_UPDATE,
            data.get(ATTR_NEXT_BEST_IN_UPDATE, DEFAULT_UPDATE_FREQUENCY),
        )
        next_period_in_update = options.get(
            ATTR_NEXT_PERIOD_IN_UPDATE,
            data.get(ATTR_NEXT_PERIOD_IN_UPDATE, DEFAULT_UPDATE_FREQUENCY),
        )
        next_power_period_in_update = options.get(
            ATTR_NEXT_POWER_PERIOD_IN_UPDATE,
            data.get(ATTR_NEXT_POWER_PERIOD_IN_UPDATE, DEFAULT_UPDATE_FREQUENCY),
        )
        holiday_source = normalize_holiday_source(
            options.get(
                ATTR_HOLIDAY_SOURCE,
                data.get(ATTR_HOLIDAY_SOURCE, DEFAULT_HOLIDAY_SOURCE),
            )
        )
        api_token = options.get(CONF_API_TOKEN, data.get(CONF_API_TOKEN))
        enable_private_api = options.get(ATTR_ENABLE_PRIVATE_API)
        if enable_private_api is None:
            enable_private_api = options.get(LEGACY_ATTR_ENABLE_INJECTION_PRICE)
        if enable_private_api is None:
            enable_private_api = data.get(ATTR_ENABLE_PRIVATE_API)
        if enable_private_api is None:
            enable_private_api = data.get(LEGACY_ATTR_ENABLE_INJECTION_PRICE)
        if enable_private_api is None:
            enable_private_api = (
                bool(api_token) if api_token else DEFAULT_ENABLE_PRIVATE_API
            )

        schema = vol.Schema(
            {
                vol.Required(ATTR_POWER_P1, default=power_p1): VALID_POWER,
                vol.Required(ATTR_POWER_P3, default=power_p3): VALID_POWER,
                vol.Required(
                    ATTR_BETTER_PRICE_TARGET, default=better_price_target
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(BETTER_PRICE_TARGETS),
                        translation_key="better_price_target",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    ATTR_NEXT_PRICE_IN_UPDATE, default=next_price_in_update
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(UPDATE_FREQUENCY_OPTIONS),
                        translation_key="update_frequency",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    ATTR_NEXT_BEST_IN_UPDATE, default=next_best_in_update
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(UPDATE_FREQUENCY_OPTIONS),
                        translation_key="update_frequency",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    ATTR_NEXT_PERIOD_IN_UPDATE, default=next_period_in_update
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(UPDATE_FREQUENCY_OPTIONS),
                        translation_key="update_frequency",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    ATTR_NEXT_POWER_PERIOD_IN_UPDATE,
                    default=next_power_period_in_update,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(UPDATE_FREQUENCY_OPTIONS),
                        translation_key="update_frequency",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(ATTR_HOLIDAY_SOURCE, default=holiday_source): SelectSelector(
                    SelectSelectorConfig(
                        options=list(HOLIDAY_SOURCES),
                        translation_key="holiday_source",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(ATTR_ENABLE_PRIVATE_API, default=enable_private_api): bool,
            }
        )

        if user_input is not None:
            self._power_p1 = user_input[ATTR_POWER_P1]
            self._power_p3 = user_input[ATTR_POWER_P3]
            self._better_price_target = user_input[ATTR_BETTER_PRICE_TARGET]
            self._next_price_in_update = user_input[ATTR_NEXT_PRICE_IN_UPDATE]
            self._next_best_in_update = user_input[ATTR_NEXT_BEST_IN_UPDATE]
            self._next_period_in_update = user_input[ATTR_NEXT_PERIOD_IN_UPDATE]
            self._next_power_period_in_update = user_input[
                ATTR_NEXT_POWER_PERIOD_IN_UPDATE
            ]
            self._holiday_source = user_input[ATTR_HOLIDAY_SOURCE]
            self._enable_private_api = user_input[ATTR_ENABLE_PRIVATE_API]
            if self._enable_private_api:
                existing_token = options.get(CONF_API_TOKEN, data.get(CONF_API_TOKEN))
                if existing_token:
                    return self.async_create_entry(
                        title="",
                        data={
                            ATTR_POWER_P1: self._power_p1,
                            ATTR_POWER_P3: self._power_p3,
                            ATTR_BETTER_PRICE_TARGET: self._better_price_target,
                            ATTR_NEXT_PRICE_IN_UPDATE: self._next_price_in_update,
                            ATTR_NEXT_BEST_IN_UPDATE: self._next_best_in_update,
                            ATTR_NEXT_PERIOD_IN_UPDATE: self._next_period_in_update,
                            ATTR_NEXT_POWER_PERIOD_IN_UPDATE: (
                                self._next_power_period_in_update
                            ),
                            ATTR_HOLIDAY_SOURCE: self._holiday_source,
                            ATTR_ENABLE_PRIVATE_API: self._enable_private_api,
                            CONF_API_TOKEN: existing_token,
                        },
                    )
                return await self.async_step_api_token(user_input)
            return self.async_create_entry(
                title="",
                data={
                    ATTR_POWER_P1: self._power_p1,
                    ATTR_POWER_P3: self._power_p3,
                    ATTR_BETTER_PRICE_TARGET: self._better_price_target,
                    ATTR_NEXT_PRICE_IN_UPDATE: self._next_price_in_update,
                    ATTR_NEXT_BEST_IN_UPDATE: self._next_best_in_update,
                    ATTR_NEXT_PERIOD_IN_UPDATE: self._next_period_in_update,
                    ATTR_NEXT_POWER_PERIOD_IN_UPDATE: (
                        self._next_power_period_in_update
                    ),
                    ATTR_HOLIDAY_SOURCE: self._holiday_source,
                    ATTR_ENABLE_PRIVATE_API: self._enable_private_api,
                    CONF_API_TOKEN: None,
                },
            )

        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_api_token(self, user_input: dict[str, Any] | None = None):
        """Handle optional API token step for extra sensors."""
        api_token = user_input.get(CONF_API_TOKEN) if user_input else None
        if user_input is not None and api_token:
            return self.async_create_entry(
                title="",
                data={
                    ATTR_POWER_P1: self._power_p1,
                    ATTR_POWER_P3: self._power_p3,
                    ATTR_BETTER_PRICE_TARGET: self._better_price_target,
                    ATTR_NEXT_PRICE_IN_UPDATE: self._next_price_in_update,
                    ATTR_NEXT_BEST_IN_UPDATE: self._next_best_in_update,
                    ATTR_NEXT_PERIOD_IN_UPDATE: self._next_period_in_update,
                    ATTR_NEXT_POWER_PERIOD_IN_UPDATE: (
                        self._next_power_period_in_update
                    ),
                    ATTR_HOLIDAY_SOURCE: self._holiday_source,
                    ATTR_ENABLE_PRIVATE_API: self._enable_private_api,
                    CONF_API_TOKEN: api_token,
                },
            )

        default_token = self.config_entry.options.get(
            CONF_API_TOKEN, self.config_entry.data.get(CONF_API_TOKEN)
        )

        schema = vol.Schema({vol.Required(CONF_API_TOKEN, default=default_token): str})

        return self.async_show_form(
            step_id="api_token",
            data_schema=schema,
            description_placeholders={"mail_to_link": _MAIL_TO_LINK},
        )


class TariffSelectorConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle config flow for PVPC Next."""

    VERSION = 7
    _name: str | None = None
    _tariff: str | None = None
    _power_p1: float | None = None
    _power_p3: float | None = None
    _better_price_target: str | None = None
    _enable_private_api: bool | None = None
    _next_price_in_update: str | None = None
    _next_best_in_update: str | None = None
    _next_period_in_update: str | None = None
    _next_power_period_in_update: str | None = None
    _holiday_source: str | None = None
    _api_token: str | None = None
    _api: PVPCData | None = None

    @staticmethod
    @callback
    def async_get_options_flow(_config_entry: ConfigEntry):
        """Return the options flow handler."""
        return PVPCOptionsFlowHandler()

    def is_matching(self, other_flow: ConfigFlow) -> bool:
        """Return True if another flow is configuring the same tariff."""
        return (
            isinstance(other_flow, TariffSelectorConfigFlow)
            and self._tariff is not None
            and self._tariff == getattr(other_flow, "_tariff", None)
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Initial configuration step."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[ATTR_TARIFF])
            self._abort_if_unique_id_configured()

            self._name = user_input[CONF_NAME]
            self._tariff = user_input[ATTR_TARIFF]
            self._power_p1 = user_input[ATTR_POWER_P1]
            self._power_p3 = user_input[ATTR_POWER_P3]
            self._better_price_target = user_input[ATTR_BETTER_PRICE_TARGET]
            self._next_price_in_update = user_input[ATTR_NEXT_PRICE_IN_UPDATE]
            self._next_best_in_update = user_input[ATTR_NEXT_BEST_IN_UPDATE]
            self._next_period_in_update = user_input[ATTR_NEXT_PERIOD_IN_UPDATE]
            self._next_power_period_in_update = user_input[
                ATTR_NEXT_POWER_PERIOD_IN_UPDATE
            ]
            self._holiday_source = user_input[ATTR_HOLIDAY_SOURCE]
            self._enable_private_api = user_input[ATTR_ENABLE_PRIVATE_API]

            if self._enable_private_api:
                return await self.async_step_api_token()
            return self.async_create_entry(
                title=self._name,
                data={
                    CONF_NAME: self._name,
                    ATTR_TARIFF: self._tariff,
                    ATTR_POWER_P1: self._power_p1,
                    ATTR_POWER_P3: self._power_p3,
                    ATTR_BETTER_PRICE_TARGET: self._better_price_target,
                    ATTR_NEXT_PRICE_IN_UPDATE: self._next_price_in_update,
                    ATTR_NEXT_BEST_IN_UPDATE: self._next_best_in_update,
                    ATTR_NEXT_PERIOD_IN_UPDATE: self._next_period_in_update,
                    ATTR_NEXT_POWER_PERIOD_IN_UPDATE: (
                        self._next_power_period_in_update
                    ),
                    ATTR_HOLIDAY_SOURCE: self._holiday_source,
                    ATTR_ENABLE_PRIVATE_API: self._enable_private_api,
                    CONF_API_TOKEN: None,
                },
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(ATTR_TARIFF, default=DEFAULT_TARIFF): VALID_TARIFF,
                vol.Required(ATTR_POWER_P1, default=DEFAULT_POWER_KW): VALID_POWER,
                vol.Required(ATTR_POWER_P3, default=DEFAULT_POWER_KW): VALID_POWER,
                vol.Required(
                    ATTR_BETTER_PRICE_TARGET, default=DEFAULT_BETTER_PRICE_TARGET
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(BETTER_PRICE_TARGETS),
                        translation_key="better_price_target",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    ATTR_NEXT_PRICE_IN_UPDATE, default=DEFAULT_UPDATE_FREQUENCY
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(UPDATE_FREQUENCY_OPTIONS),
                        translation_key="update_frequency",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    ATTR_NEXT_BEST_IN_UPDATE, default=DEFAULT_UPDATE_FREQUENCY
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(UPDATE_FREQUENCY_OPTIONS),
                        translation_key="update_frequency",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    ATTR_NEXT_PERIOD_IN_UPDATE, default=DEFAULT_UPDATE_FREQUENCY
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(UPDATE_FREQUENCY_OPTIONS),
                        translation_key="update_frequency",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    ATTR_NEXT_POWER_PERIOD_IN_UPDATE,
                    default=DEFAULT_UPDATE_FREQUENCY,
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(UPDATE_FREQUENCY_OPTIONS),
                        translation_key="update_frequency",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    ATTR_HOLIDAY_SOURCE, default=DEFAULT_HOLIDAY_SOURCE
                ): SelectSelector(
                    SelectSelectorConfig(
                        options=list(HOLIDAY_SOURCES),
                        translation_key="holiday_source",
                        mode=SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    ATTR_ENABLE_PRIVATE_API,
                    default=DEFAULT_ENABLE_PRIVATE_API,
                ): bool,
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_api_token(self, user_input: dict[str, Any] | None = None):
        """Optional step to set API token."""
        if user_input is not None:
            self._api_token = user_input[CONF_API_TOKEN]
            return await self._async_verify("api_token")

        schema = vol.Schema({vol.Required(CONF_API_TOKEN, default=self._api_token): str})
        return self.async_show_form(
            step_id="api_token",
            data_schema=schema,
            description_placeholders={"mail_to_link": _MAIL_TO_LINK},
        )

    async def _async_verify(self, step_id: str):
        """Verify API token if used."""
        errors: dict[str, str] = {}
        auth_ok = True

        if self._api_token:
            if not self._api:
                self._api = PVPCData(session=async_get_clientsession(self.hass))
            auth_ok = await self._api.check_api_token(dt_util.utcnow(), self._api_token)

        if not auth_ok:
            errors["base"] = "invalid_auth"
            return self.async_show_form(step_id=step_id, errors=errors)

        data = {
            CONF_NAME: self._name,
            ATTR_TARIFF: self._tariff,
            ATTR_POWER_P1: self._power_p1,
            ATTR_POWER_P3: self._power_p3,
            ATTR_BETTER_PRICE_TARGET: self._better_price_target,
            ATTR_NEXT_PRICE_IN_UPDATE: self._next_price_in_update,
            ATTR_NEXT_BEST_IN_UPDATE: self._next_best_in_update,
            ATTR_NEXT_PERIOD_IN_UPDATE: self._next_period_in_update,
            ATTR_NEXT_POWER_PERIOD_IN_UPDATE: self._next_power_period_in_update,
            ATTR_HOLIDAY_SOURCE: normalize_holiday_source(self._holiday_source),
            ATTR_ENABLE_PRIVATE_API: self._enable_private_api,
            CONF_API_TOKEN: self._api_token,
        }

        if self.source == SOURCE_REAUTH:
            return self.async_update_reload_and_abort(None, data=data)

        assert self._name is not None
        return self.async_create_entry(title=self._name, data=data)

    async def async_step_reauth(self, entry_data: Mapping[str, Any]):
        """Re-authentication step."""
        self._api_token = entry_data.get(CONF_API_TOKEN)
        self._name = entry_data[CONF_NAME]
        self._tariff = entry_data[ATTR_TARIFF]
        self._power_p1 = entry_data.get(ATTR_POWER_P1, entry_data.get(LEGACY_ATTR_POWER))
        self._power_p3 = entry_data.get(
            ATTR_POWER_P3,
            entry_data.get(
                LEGACY_ATTR_POWER_P2_P3, entry_data.get(LEGACY_ATTR_POWER_P3)
            ),
        )
        self._better_price_target = entry_data.get(
            ATTR_BETTER_PRICE_TARGET, DEFAULT_BETTER_PRICE_TARGET
        )
        self._holiday_source = entry_data.get(
            ATTR_HOLIDAY_SOURCE, DEFAULT_HOLIDAY_SOURCE
        )
        self._enable_private_api = entry_data.get(
            ATTR_ENABLE_PRIVATE_API,
            entry_data.get(
                LEGACY_ATTR_ENABLE_INJECTION_PRICE,
                self._api_token is not None or DEFAULT_ENABLE_PRIVATE_API,
            ),
        )
        if self._power_p1 is None:
            self._power_p1 = DEFAULT_POWER_KW
        if self._power_p3 is None:
            self._power_p3 = DEFAULT_POWER_KW
        if self._holiday_source not in HOLIDAY_SOURCES:
            self._holiday_source = DEFAULT_HOLIDAY_SOURCE
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None):
        """Confirm re-authentication."""
        schema = vol.Schema(
            {
                vol.Required(CONF_API_TOKEN, default=self._api_token): str,
            }
        )
        if user_input:
            self._api_token = user_input.get(CONF_API_TOKEN)
            return await self._async_verify("reauth_confirm")
        return self.async_show_form(step_id="reauth_confirm", data_schema=schema)
