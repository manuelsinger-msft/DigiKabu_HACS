"""UI configuration and reauthentication for student accounts."""

from collections.abc import Mapping
from typing import Any

import probatio as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .api import (
    DigiKabuApi,
    DigiKabuAuthError,
    DigiKabuConnectionError,
    DigiKabuError,
    DigiKabuResponseError,
)
from .const import CONF_API_KEY, DOMAIN

_PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))


def _schema(username: str | None = None, *, reauth: bool = False) -> vol.Schema:
    fields = {}
    if not reauth:
        fields[vol.Required(CONF_USERNAME, default=username or vol.UNDEFINED)] = (
            TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))
        )
    fields[vol.Required(CONF_PASSWORD)] = _PASSWORD
    fields[vol.Optional(CONF_API_KEY)] = _PASSWORD
    return vol.Schema(fields)


class DigiKabuConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure one account per exact username without exposing tokens."""

    VERSION = 1

    async def _validate(self, data: Mapping[str, Any]) -> dict[str, str]:
        if not data[CONF_USERNAME].strip() or not data[CONF_PASSWORD]:
            return {"base": "invalid_auth"}
        client = DigiKabuApi(
            async_get_clientsession(self.hass),
            data[CONF_USERNAME],
            data[CONF_PASSWORD],
            data.get(CONF_API_KEY, ""),
        )
        try:
            await client.async_authenticate()
            # This is the one endpoint explicitly documented as student-only.
            await client.async_get_absences()
        except DigiKabuAuthError:
            return {"base": "invalid_auth"}
        except DigiKabuConnectionError:
            return {"base": "cannot_connect"}
        except DigiKabuResponseError:
            return {"base": "invalid_response"}
        except DigiKabuError:
            return {"base": "api_error"}
        return {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            user_input = {
                **user_input,
                CONF_USERNAME: user_input[CONF_USERNAME].strip(),
            }
            if not (errors := await self._validate(user_input)):
                await self.async_set_unique_id(user_input[CONF_USERNAME])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_USERNAME], data=user_input
                )
        return self.async_show_form(
            step_id="user",
            data_schema=_schema((user_input or {}).get(CONF_USERNAME)),
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Mapping[str, Any]
    ) -> ConfigFlowResult:
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        entry = self._get_reauth_entry()
        errors = {}
        if user_input is not None:
            data = {**entry.data, CONF_PASSWORD: user_input[CONF_PASSWORD]}
            if CONF_API_KEY in user_input:
                data[CONF_API_KEY] = user_input[CONF_API_KEY]
            if not (errors := await self._validate(data)):
                return self.async_update_reload_and_abort(entry, data_updates=data)
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=_schema(reauth=True),
            errors=errors,
        )
