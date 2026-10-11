"""Exercise real HA objects with only the remote client mocked."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import probatio
import pytest
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers.update_coordinator import UpdateFailed

from custom_components.digikabu import (
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.digikabu.api import (
    DigiKabuAuthError,
    DigiKabuConnectionError,
    DigiKabuResponseError,
)
from custom_components.digikabu.const import DOMAIN, ENDPOINTS
from custom_components.digikabu.coordinator import (
    DigiKabuCoordinator,
    DigiKabuData,
    EndpointData,
)
from custom_components.digikabu.sensor import DigiKabuSensor


async def test_setup_and_unload(hass, entry, mock_api):
    with (
        patch("custom_components.digikabu.DigiKabuApi", return_value=mock_api),
        patch("custom_components.digikabu.async_get_clientsession"),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new=AsyncMock()
        ) as forward,
        patch.object(
            hass.config_entries,
            "async_unload_platforms",
            new=AsyncMock(return_value=True),
        ) as unload,
    ):
        assert await async_setup(hass, {})
        assert await async_setup_entry(hass, entry)
        forward.assert_awaited_once()
        assert set(entry.runtime_data.coordinators) == set(ENDPOINTS)
        mock_api.async_authenticate.assert_awaited_once()
        assert mock_api.async_submit_excuse.await_count == 0
        assert mock_api.async_set_email.await_count == 0
        assert await async_unload_entry(hass, entry)
        unload.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (DigiKabuAuthError("bad login"), ConfigEntryAuthFailed),
        (DigiKabuConnectionError("offline"), ConfigEntryNotReady),
        (DigiKabuResponseError("bad JSON"), ConfigEntryNotReady),
    ],
)
async def test_initial_auth_errors(hass, entry, mock_api, error, expected):
    mock_api.async_authenticate.side_effect = error
    with (
        patch("custom_components.digikabu.DigiKabuApi", return_value=mock_api),
        patch("custom_components.digikabu.async_get_clientsession"),
        pytest.raises(expected),
    ):
        await async_setup_entry(hass, entry)


async def test_endpoint_failure_isolated_and_recovers(hass, entry, mock_api):
    coordinator = DigiKabuCoordinator(hass, entry, mock_api, "absences")
    sensor = DigiKabuSensor(entry, coordinator)
    mock_api.async_get_absences.side_effect = DigiKabuConnectionError("offline")
    await coordinator.async_refresh()
    assert not sensor.available
    assert sensor.native_value is None
    assert isinstance(coordinator.last_exception, UpdateFailed)

    other = DigiKabuCoordinator(hass, entry, mock_api, "timetable")
    await other.async_refresh()
    assert other.last_update_success

    mock_api.async_get_absences.side_effect = None
    await coordinator.async_refresh()
    assert sensor.available
    assert sensor.native_value.tzinfo is not None
    assert sensor.extra_state_attributes == {"response": {"overview": []}}


async def test_coordinator_auth_failure(hass, entry, mock_api):
    coordinator = DigiKabuCoordinator(hass, entry, mock_api, "absences")
    mock_api.async_get_absences.side_effect = DigiKabuAuthError("rejected")
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_sensor_stable_id_and_raw_data(hass, entry, mock_api):
    coordinator = DigiKabuCoordinator(hass, entry, mock_api, "timetable")
    response = [{"no_assumed_model": {"value": 1}}]
    now = datetime(2026, 10, 11, tzinfo=UTC)
    coordinator.async_set_updated_data(EndpointData(response, now))
    sensor = DigiKabuSensor(entry, coordinator)
    assert sensor.unique_id == f"{entry.entry_id}_timetable"
    assert sensor.native_value == now
    assert sensor.extra_state_attributes == {"response": response}
    remove = coordinator.async_add_listener(lambda: None)
    assert coordinator._unsub_refresh is not None
    remove()
    assert coordinator._unsub_refresh is None


async def prepare_services(hass, entry, mock_api):
    entry.runtime_data = DigiKabuData(
        mock_api,
        {key: DigiKabuCoordinator(hass, entry, mock_api, key) for key in ENDPOINTS},
    )
    await async_setup(hass, {})
    return {"config_entry_id": entry.entry_id}


@pytest.mark.parametrize(
    ("name", "method", "extra", "args"),
    [
        ("get_absences", "async_get_absences", {}, ()),
        ("get_timetable", "async_get_timetable", {"anzahl": 3}, (None, 3)),
        ("get_exams", "async_get_exams", {"monat": "12"}, (12,)),
        ("get_appointments", "async_get_appointments", {}, ()),
    ],
)
async def test_read_actions(hass, entry, mock_api, name, method, extra, args):
    data = await prepare_services(hass, entry, mock_api)
    result = await hass.services.async_call(
        DOMAIN, name, {**data, **extra}, blocking=True, return_response=True
    )
    getattr(mock_api, method).assert_awaited_once_with(*args)
    assert result == {"data": getattr(mock_api, method).return_value}


async def test_email_requires_both_fields(hass, entry, mock_api):
    data = await prepare_services(hass, entry, mock_api)
    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN, "set_email", {**data, "email1": "a@example.invalid"}, blocking=True
        )
    mock_api.async_set_email.assert_not_awaited()
    await hass.services.async_call(
        DOMAIN,
        "set_email",
        {**data, "email1": "a@example.invalid", "email2": None},
        blocking=True,
    )
    mock_api.async_set_email.assert_awaited_once_with("a@example.invalid", None)


async def test_unloaded_or_wrong_entry_rejected(hass, entry, mock_api):
    await prepare_services(hass, entry, mock_api)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_email",
            {"config_entry_id": "missing", "email1": None, "email2": None},
            blocking=True,
        )
    mock_api.async_set_email.assert_not_awaited()


@pytest.mark.parametrize(
    ("now", "requested", "allowed"),
    [
        ("2026-10-11T06:59:59+00:00", "2026-10-11T00:00:00", True),
        ("2026-10-11T07:00:00+00:00", "2026-10-11T00:00:00", False),
        ("2026-10-11T12:00:00+00:00", "2026-10-12T00:00:00", True),
        ("2026-10-11T12:00:00+00:00", "2026-10-13T00:00:00", False),
        ("2026-10-11T12:00:00+00:00", "2026-10-10T00:00:00", False),
        ("2026-10-25T07:59:59+00:00", "2026-10-25T00:00:00", True),
        ("2026-10-25T08:00:00+00:00", "2026-10-25T00:00:00", False),
    ],
)
async def test_excuse_school_timezone(hass, entry, mock_api, now, requested, allowed):
    data = await prepare_services(hass, entry, mock_api)
    data.update({"ab_datum": requested, "dauer": 2, "grund": None})
    with patch(
        "custom_components.digikabu.services.dt_util.utcnow",
        return_value=datetime.fromisoformat(now),
    ):
        if allowed:
            await hass.services.async_call(DOMAIN, "submit_excuse", data, blocking=True)
            start, duration, reason = mock_api.async_submit_excuse.call_args.args
            assert start.hour == 0
            assert str(start.tzinfo) == "Europe/Berlin"
            assert duration == 2
            assert reason is None
        else:
            with pytest.raises(ServiceValidationError):
                await hass.services.async_call(
                    DOMAIN, "submit_excuse", data, blocking=True
                )
            mock_api.async_submit_excuse.assert_not_awaited()


async def test_write_unknown_outcome_is_reported(hass, entry, mock_api):
    data = await prepare_services(hass, entry, mock_api)
    mock_api.async_set_email.side_effect = DigiKabuConnectionError("outcome is unknown")
    with pytest.raises(HomeAssistantError, match="outcome is unknown"):
        await hass.services.async_call(
            DOMAIN, "set_email", {**data, "email1": None, "email2": None}, blocking=True
        )
    assert mock_api.async_set_email.await_count == 1


@pytest.mark.parametrize("value", [True, 1.5, 0, 4])
async def test_excuse_duration_schema_rejects_invalid(hass, entry, mock_api, value):
    data = await prepare_services(hass, entry, mock_api)
    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(
            DOMAIN,
            "submit_excuse",
            {**data, "ab_datum": "2026-10-12T00:00:00", "dauer": value},
            blocking=True,
        )
    mock_api.async_submit_excuse.assert_not_awaited()


async def test_service_auth_failure_requests_reauth(hass, entry, mock_api):
    data = await prepare_services(hass, entry, mock_api)
    mock_api.async_get_absences.side_effect = DigiKabuAuthError("rejected")
    with (
        patch.object(type(entry), "async_start_reauth") as reauth,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN, "get_absences", data, blocking=True, return_response=True
        )
    reauth.assert_called_once_with(hass)
