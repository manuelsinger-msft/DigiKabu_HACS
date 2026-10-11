"""Student-only DigiKabu integration."""

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import DigiKabuApi, DigiKabuAuthError, DigiKabuError
from .const import CONF_API_KEY, DOMAIN, ENDPOINTS
from .coordinator import DigiKabuConfigEntry, DigiKabuCoordinator, DigiKabuData
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [Platform.SENSOR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register actions even when no account is loaded."""
    async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: DigiKabuConfigEntry) -> bool:
    """Authenticate and set up independently available endpoint sensors."""
    client = DigiKabuApi(
        async_get_clientsession(hass),
        entry.data[CONF_USERNAME],
        entry.data[CONF_PASSWORD],
        entry.data.get(CONF_API_KEY, ""),
    )
    try:
        await client.async_authenticate()
    except DigiKabuAuthError as err:
        raise ConfigEntryAuthFailed("DigiKabu rejected authentication") from err
    except DigiKabuError as err:
        raise ConfigEntryNotReady(str(err)) from err

    coordinators = {
        endpoint: DigiKabuCoordinator(hass, entry, client, endpoint)
        for endpoint in ENDPOINTS
    }
    entry.runtime_data = DigiKabuData(client, coordinators)
    for coordinator in coordinators.values():
        # A read failure leaves only this sensor unavailable and is logged by HA.
        await coordinator.async_refresh()
        if coordinator.last_exception and isinstance(
            coordinator.last_exception, ConfigEntryAuthFailed
        ):
            raise coordinator.last_exception

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DigiKabuConfigEntry) -> bool:
    """Unsubscribe polling; HA owns and closes the shared HTTP session."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
