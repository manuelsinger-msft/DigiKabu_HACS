"""Fixtures using real HA 2026.10.1 and mocked external HTTP only."""

from types import MappingProxyType
from unittest.mock import AsyncMock

import pytest
from aiohttp import ClientSession
from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_registry

from custom_components.digikabu.api import DigiKabuApi
from custom_components.digikabu.const import DOMAIN


@pytest.fixture
async def hass(tmp_path):
    instance = HomeAssistant(str(tmp_path))
    instance.config_entries = ConfigEntries(instance, {})
    await instance.config_entries.async_initialize()
    device_registry.async_setup(instance)
    await device_registry.async_load(instance)
    await entity_registry.async_load(instance)
    yield instance
    await instance.async_block_till_done()
    await instance.async_stop()


@pytest.fixture
def entry(hass):
    config_entry = ConfigEntry(
        domain=DOMAIN,
        title="student",
        unique_id="student",
        version=1,
        minor_version=1,
        data={"username": "student", "password": "test-password"},
        options={},
        source="user",
        discovery_keys=MappingProxyType({}),
        subentries_data=[],
        state=ConfigEntryState.LOADED,
    )
    hass.config_entries._entries[config_entry.entry_id] = config_entry
    return config_entry


@pytest.fixture
async def session():
    async with ClientSession() as session:
        yield session


@pytest.fixture
async def client():
    async with ClientSession() as session:
        yield DigiKabuApi(session, "student", "test-password")


@pytest.fixture
def mock_api():
    api = AsyncMock(spec=DigiKabuApi)
    api.async_get_absences.return_value = {"overview": []}
    api.async_get_timetable.return_value = [{"datum": "2026-10-11"}]
    api.async_get_exams.return_value = []
    api.async_get_appointments.return_value = []
    return api
