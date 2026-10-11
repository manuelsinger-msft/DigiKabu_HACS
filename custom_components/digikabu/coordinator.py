"""Independent polling of each student read endpoint."""

import logging
from dataclasses import dataclass
from datetime import datetime

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import DigiKabuApi, DigiKabuAuthError, DigiKabuError, JSONValue
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class EndpointData:
    """Response without inferred fields, plus its successful retrieval time."""

    response: JSONValue
    fetched_at: datetime


class DigiKabuCoordinator(DataUpdateCoordinator[EndpointData]):
    """One failed endpoint should not make other student data unavailable."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: DigiKabuApi,
        endpoint: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{endpoint}",
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client
        self.endpoint = endpoint

    async def _async_update_data(self) -> EndpointData:
        try:
            match self.endpoint:
                case "absences":
                    result = await self.client.async_get_absences()
                case "timetable":
                    result = await self.client.async_get_timetable()
                case "exams":
                    result = await self.client.async_get_exams()
                case "appointments":
                    result = await self.client.async_get_appointments()
                case _:
                    raise ValueError(f"Unknown DigiKabu endpoint: {self.endpoint}")
        except DigiKabuAuthError as err:
            raise ConfigEntryAuthFailed(
                "DigiKabu credentials are no longer valid"
            ) from err
        except DigiKabuError as err:
            raise UpdateFailed(str(err)) from err
        return EndpointData(result, dt_util.utcnow())


@dataclass
class DigiKabuData:
    """Runtime objects belonging to one student account."""

    client: DigiKabuApi
    coordinators: dict[str, DigiKabuCoordinator]


type DigiKabuConfigEntry = ConfigEntry[DigiKabuData]
