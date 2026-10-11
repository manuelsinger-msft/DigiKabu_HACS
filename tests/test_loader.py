"""Load and unload the integration through the actual Home Assistant framework."""

import shutil
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from homeassistant import loader
from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import frame
from homeassistant.helpers.entity_registry import async_get

from custom_components.digikabu.api import DigiKabuConnectionError
from custom_components.digikabu.timetable_cache import TimetableCache


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
    hass.config.components.add("http")
    hass.http = MagicMock()
    entry._async_set_state(hass, ConfigEntryState.NOT_LOADED, None)
    with (
        patch("custom_components.digikabu.DigiKabuApi", return_value=mock_api),
        patch(
            "custom_components.digikabu.async_get_clientsession",
            return_value=session,
        ),
        patch(
            "custom_components.digikabu.timetable_cache.dt_util.utcnow",
            return_value=datetime.fromisoformat("2026-10-11T12:00:00+00:00"),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        registry = async_get(hass)
        sensors = [
            entity
            for entity in registry.entities.values()
            if entity.config_entry_id == entry.entry_id and entity.domain == "sensor"
        ]
        assert len(sensors) == 6
        calendars = [
            entity
            for entity in registry.entities.values()
            if entity.config_entry_id == entry.entry_id and entity.domain == "calendar"
        ]
        assert len(calendars) == 2
        for entity in calendars:
            assert hass.states.get(entity.entity_id).state == "off"
        for entity in sensors:
            state = hass.states.get(entity.entity_id)
            assert state is not None
            if "_card_week_" in entity.unique_id:
                assert state.state == "unavailable"
            elif absences_fail and entity.unique_id.endswith("_absences"):
                assert state.state == "unavailable"
            else:
                assert state.state not in ("unknown", "unavailable")
                assert "response" in state.attributes
            if entity.unique_id.endswith("_timetable"):
                assert "Timetable updated" in state.attributes["friendly_name"]
            assert "test-password" not in str(state.attributes)
        mock_api.async_get_timetable.return_value = [
            {
                "datum": "12.10.2026",
                "anfStd": 2,
                "endStd": 3,
                "uFachBez": "Testfach",
                "lehrer": "TEST",
                "raumLongtext": "R0",
                "gruppe": "1/1",
            }
        ]
        await hass.services.async_call(
            "digikabu",
            "get_card_timetable",
            {
                "config_entry_id": entry.entry_id,
                "datum": "2026-10-12T00:00:00",
                "weeks": 2,
            },
            blocking=True,
            return_response=True,
        )
        await hass.async_block_till_done()
        for entity in sensors:
            if "_card_week_" in entity.unique_id:
                state = hass.states.get(entity.entity_id)
                assert state.state not in ("unknown", "unavailable")
                assert len(state.attributes["rows"]) == 11
                assert len(state.attributes["days"]) == 5
                assert "Card timetable week" in state.attributes["friendly_name"]
                assert state.attributes["rows"][1]["cell_styles"] == [None] * 5
        mock_api.async_get_timetable.return_value[0]["lehrer"] = "NEW"
        await hass.services.async_call(
            "digikabu",
            "get_card_timetable",
            {
                "config_entry_id": entry.entry_id,
                "datum": "2026-10-12T00:00:00",
                "weeks": 2,
            },
            blocking=True,
            return_response=True,
        )
        for entity in sensors:
            if entity.unique_id.endswith("_card_week_1"):
                rows = hass.states.get(entity.entity_id).attributes["rows"]
                assert "Geaendert" in rows[1]["cells"][0]
                assert rows[1]["cell_styles"][0]["bg"] == "#f9a825"
        coordinators = list(entry.runtime_data.coordinators.values())
        assert all(coordinator._unsub_refresh for coordinator in coordinators)
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert all(coordinator._unsub_refresh is None for coordinator in coordinators)
        assert mock_api.async_submit_excuse.await_count == 0
        assert mock_api.async_set_email.await_count == 0
        assert not session.closed
        cache = TimetableCache(hass, entry.entry_id)
        assert await cache.store.async_load() is not None
        assert await hass.config_entries.async_remove(entry.entry_id)
        assert await cache.store.async_load() is None
