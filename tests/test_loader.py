"""Load and unload the integration through the actual Home Assistant framework."""

import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from homeassistant import loader
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import frame
from homeassistant.helpers.entity_registry import async_get

from custom_components.digikabu.api import DigiKabuConnectionError


@pytest.mark.parametrize("absences_fail", [False, True])
async def test_real_ha_setup_and_unload(hass, entry, mock_api, session, absences_fail):
    if absences_fail:
        mock_api.async_get_absences.side_effect = DigiKabuConnectionError("offline")
    shutil.copytree(
        Path(__file__).parents[1] / "custom_components" / "digikabu",
        Path(hass.config.path("custom_components")) / "digikabu",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    loader.async_setup(hass)
    frame.async_setup(hass)
    entry._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)
    with (
        patch("custom_components.digikabu.DigiKabuApi", return_value=mock_api),
        patch(
            "custom_components.digikabu.async_get_clientsession",
            return_value=session,
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = async_get(hass)
        sensors = [
            entity
            for entity in registry.entities.values()
            if entity.config_entry_id == entry.entry_id
        ]
        assert len(sensors) == 4
        for entity in sensors:
            state = hass.states.get(entity.entity_id)
            assert state is not None
            if absences_fail and entity.unique_id.endswith("_absences"):
                assert state.state == "unavailable"
            else:
                assert state.state not in ("unknown", "unavailable")
                assert "response" in state.attributes
            if entity.unique_id.endswith("_timetable"):
                assert "Timetable updated" in state.attributes["friendly_name"]
            assert "test-password" not in str(state.attributes)
        coordinators = list(entry.runtime_data.coordinators.values())
        assert all(coordinator._unsub_refresh for coordinator in coordinators)
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert all(coordinator._unsub_refresh is None for coordinator in coordinators)
        assert mock_api.async_submit_excuse.await_count == 0
        assert mock_api.async_set_email.await_count == 0
        assert not session.closed
