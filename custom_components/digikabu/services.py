"""Explicit account-scoped student API actions."""

from datetime import datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import probatio as vol
from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import service
from homeassistant.util import dt as dt_util

from .api import DigiKabuAuthError, DigiKabuError, JSONValue
from .const import DOMAIN
from .coordinator import DigiKabuConfigEntry

_SCHOOL_TIMEZONE = ZoneInfo("Europe/Berlin")
_ENTRY_FIELD = {vol.Required("config_entry_id"): cv.string}


def _integer(value: Any) -> int:
    if isinstance(value, bool) or (isinstance(value, float) and not value.is_integer()):
        raise vol.Invalid("Expected a whole number")
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError) as err:
        raise vol.Invalid("Expected a whole number") from err


def _validate_excuse(ab_datum: datetime) -> datetime:
    if ab_datum.tzinfo is None:
        ab_datum = ab_datum.replace(tzinfo=_SCHOOL_TIMEZONE)
    school_date = ab_datum.astimezone(_SCHOOL_TIMEZONE).date()
    now = dt_util.utcnow().astimezone(_SCHOOL_TIMEZONE)
    if school_date not in (now.date(), now.date() + timedelta(days=1)) or (
        school_date == now.date() and now.time() >= time(9)
    ):
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="invalid_excuse_date"
        )
    return datetime.combine(school_date, time.min, _SCHOOL_TIMEZONE)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register actions once, not once per config entry."""

    async def handle(call: ServiceCall) -> dict[str, JSONValue] | None:
        entry: DigiKabuConfigEntry = service.async_get_config_entry(
            hass, DOMAIN, call.data["config_entry_id"]
        )
        client = entry.runtime_data.client
        try:
            match call.service:
                case "get_absences":
                    response = await client.async_get_absences()
                case "get_timetable":
                    response = await client.async_get_timetable(
                        call.data.get("datum"), call.data["anzahl"]
                    )
                case "get_exams":
                    response = await client.async_get_exams(call.data["monat"])
                case "get_appointments":
                    response = await client.async_get_appointments()
                case "submit_excuse":
                    await client.async_submit_excuse(
                        _validate_excuse(call.data["ab_datum"]),
                        call.data["dauer"],
                        call.data.get("grund"),
                    )
                    # A refresh failure must not turn a completed write into failure.
                    await entry.runtime_data.coordinators[
                        "absences"
                    ].async_request_refresh()
                    return None
                case "set_email":
                    await client.async_set_email(
                        call.data["email1"], call.data["email2"]
                    )
                    return None
                case _:
                    raise ServiceValidationError("Unknown DigiKabu action")
        except DigiKabuAuthError as err:
            entry.async_start_reauth(hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN, translation_key="authentication_failed"
            ) from err
        except DigiKabuError as err:
            raise HomeAssistantError(str(err)) from err
        return {"data": response}

    read_schemas = {
        "get_absences": {},
        "get_timetable": {
            vol.Optional("datum"): cv.datetime,
            vol.Optional("anzahl", default=1): vol.All(_integer, vol.Range(min=1)),
        },
        "get_exams": {
            vol.Optional("monat", default=-1): vol.All(
                _integer, vol.Any(-1, vol.Range(min=1, max=12))
            ),
        },
        "get_appointments": {},
    }
    for name, fields in read_schemas.items():
        hass.services.async_register(
            DOMAIN,
            name,
            handle,
            schema=vol.Schema({**_ENTRY_FIELD, **fields}),
            supports_response=SupportsResponse.ONLY,
        )
    hass.services.async_register(
        DOMAIN,
        "submit_excuse",
        handle,
        schema=vol.Schema(
            {
                **_ENTRY_FIELD,
                vol.Required("ab_datum"): cv.datetime,
                vol.Required("dauer"): vol.All(_integer, vol.Range(min=1, max=3)),
                vol.Optional("grund"): vol.Any(None, cv.string),
            }
        ),
    )
    hass.services.async_register(
        DOMAIN,
        "set_email",
        handle,
        schema=vol.Schema(
            {
                **_ENTRY_FIELD,
                # Both fields are mandatory: omission must not clear an address.
                vol.Required("email1"): vol.Any(None, cv.string),
                vol.Required("email2"): vol.Any(None, cv.string),
            }
        ),
    )
