"""Calendar conversion and range queries with synthetic data."""

from datetime import date, datetime
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.digikabu.api import (
    DigiKabuConnectionError,
    DigiKabuResponseError,
)
from custom_components.digikabu.calendar import DigiKabuCalendar, parse_events
from custom_components.digikabu.coordinator import (
    DigiKabuCoordinator,
    DigiKabuData,
    EndpointData,
)

NOW = datetime.fromisoformat("2026-10-11T12:00:00+02:00")


def test_observed_exam_and_appointment_shapes():
    exam = parse_events([{"date": "24.11.2026", "info": "Test exam"}], "exams")[0]
    assert exam.start == date(2026, 11, 24)
    assert exam.end == date(2026, 11, 25)
    appointment = parse_events(
        [
            {
                "datumVon": "2026-10-26T00:00:00",
                "datumBis": "2026-10-26T00:00:00",
                "hinweis": "Test event",
            }
        ],
        "appointments",
    )[0]
    assert appointment.end == date(2026, 10, 27)


@pytest.mark.parametrize(
    "response,endpoint",
    [
        ({}, "exams"),
        ([{}], "exams"),
        ([{"date": "31.02.2026", "info": "Test"}], "exams"),
        ([{"date": "12.10.2026", "info": ""}], "exams"),
        (
            [
                {
                    "datumVon": "2026-10-12T12:00:00",
                    "datumBis": "2026-10-12T13:00:00",
                    "hinweis": "Test",
                }
            ],
            "appointments",
        ),
        (
            [
                {
                    "datumVon": "2026-10-12T00:00:00",
                    "datumBis": "2026-10-13T00:00:00",
                    "hinweis": "Test",
                }
            ],
            "appointments",
        ),
    ],
)
def test_unknown_shapes_fail(response, endpoint):
    with pytest.raises(DigiKabuResponseError):
        parse_events(response, endpoint)


def calendar(hass, entry, mock_api, endpoint, items):
    coordinator = DigiKabuCoordinator(hass, entry, mock_api, endpoint)
    coordinator.async_set_updated_data(EndpointData(items, NOW))
    entry.runtime_data = DigiKabuData(mock_api, {endpoint: coordinator})
    return DigiKabuCalendar(entry, coordinator)


async def test_month_requests_filter_year_and_reuse_cache(hass, entry, mock_api):
    entity = calendar(
        hass,
        entry,
        mock_api,
        "exams",
        [
            {"date": "31.10.2026", "info": "Holiday"},
        ],
    )
    mock_api.async_get_exams.return_value = [
        {"date": "24.11.2026", "info": "Test exam"},
        {"date": "24.11.2025", "info": "Old exam"},
    ]
    with patch("custom_components.digikabu.calendar.dt_util.utcnow", return_value=NOW):
        events = await entity.async_get_events(
            hass, NOW, datetime.fromisoformat("2026-12-01T00:00:00+02:00")
        )
        assert len(events) == 2
        assert mock_api.async_get_exams.await_count == 1
        assert (
            await entity.async_get_events(
                hass, NOW, datetime.fromisoformat("2026-12-01T00:00:00+02:00")
            )
            == events
        )
        assert mock_api.async_get_exams.await_count == 1
    assert entity.supported_features == 0


async def test_exclusive_range_and_next_event(hass, entry, mock_api):
    entity = calendar(
        hass,
        entry,
        mock_api,
        "appointments",
        [
            {
                "datumVon": "2026-10-12T00:00:00",
                "datumBis": "2026-10-12T00:00:00",
                "hinweis": "Test",
            },
        ],
    )
    with patch("custom_components.digikabu.calendar.dt_util.now", return_value=NOW):
        assert entity.event.start == date(2026, 10, 12)
    assert (
        await entity.async_get_events(
            hass, NOW, datetime.fromisoformat("2026-10-12T00:00:00+02:00")
        )
        == []
    )
    assert (
        await entity.async_get_events(
            hass,
            datetime.fromisoformat("2026-10-13T00:00:00+02:00"),
            datetime.fromisoformat("2026-10-14T00:00:00+02:00"),
        )
        == []
    )


async def test_failed_month_read_is_not_empty_success(hass, entry, mock_api):
    entity = calendar(hass, entry, mock_api, "exams", [])
    mock_api.async_get_exams.side_effect = DigiKabuConnectionError("offline")
    with (
        patch("custom_components.digikabu.calendar.dt_util.utcnow", return_value=NOW),
        pytest.raises(HomeAssistantError),
    ):
        await entity.async_get_events(
            hass, NOW, datetime.fromisoformat("2026-12-01T00:00:00+02:00")
        )
    assert entity._months == {}
