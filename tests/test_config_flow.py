"""Real config-flow results, duplicate-account handling and reauthentication."""

from unittest.mock import patch

import pytest
from homeassistant.data_entry_flow import AbortFlow, FlowResultType

from custom_components.digikabu.api import (
    DigiKabuAuthError,
    DigiKabuConnectionError,
    DigiKabuError,
    DigiKabuResponseError,
)
from custom_components.digikabu.config_flow import DigiKabuConfigFlow


def flow_for(hass, **context):
    flow = DigiKabuConfigFlow()
    flow.hass = hass
    flow.context = {"source": "user", **context}
    flow.handler = "digikabu"
    return flow


async def test_user_form_and_success(hass, mock_api):
    flow = flow_for(hass)
    assert (await flow.async_step_user())["type"] == FlowResultType.FORM
    with (
        patch(
            "custom_components.digikabu.config_flow.DigiKabuApi", return_value=mock_api
        ),
        patch("custom_components.digikabu.config_flow.async_get_clientsession"),
    ):
        result = await flow.async_step_user(
            {"username": "student", "password": "test-password"}
        )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"] == {"username": "student", "password": "test-password"}
    assert flow.unique_id == "student"
    mock_api.async_get_absences.assert_awaited_once()
    mock_api.async_set_email.assert_not_awaited()


async def test_duplicate(hass, entry, mock_api):
    flow = flow_for(hass)
    with (
        patch(
            "custom_components.digikabu.config_flow.DigiKabuApi", return_value=mock_api
        ),
        patch("custom_components.digikabu.config_flow.async_get_clientsession"),
        pytest.raises(AbortFlow, match="already_configured"),
    ):
        await flow.async_step_user({"username": "student", "password": "test-password"})


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (DigiKabuAuthError("rejected"), "invalid_auth"),
        (DigiKabuConnectionError("offline"), "cannot_connect"),
        (DigiKabuResponseError("bad response"), "invalid_response"),
        (DigiKabuError("HTTP 403"), "api_error"),
    ],
)
async def test_validation_errors(hass, mock_api, error, message):
    mock_api.async_authenticate.side_effect = error
    with (
        patch(
            "custom_components.digikabu.config_flow.DigiKabuApi", return_value=mock_api
        ),
        patch("custom_components.digikabu.config_flow.async_get_clientsession"),
    ):
        result = await flow_for(hass).async_step_user(
            {"username": "student", "password": "test-password"}
        )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": message}


async def test_reauth_preserves_account_and_updates_password(hass, entry, mock_api):
    flow = flow_for(hass, source="reauth", entry_id=entry.entry_id)
    with (
        patch(
            "custom_components.digikabu.config_flow.DigiKabuApi", return_value=mock_api
        ),
        patch("custom_components.digikabu.config_flow.async_get_clientsession"),
        patch.object(hass.config_entries, "async_schedule_reload") as reload,
    ):
        form = await flow.async_step_reauth(entry.data)
        assert form["step_id"] == "reauth_confirm"
        result = await flow.async_step_reauth_confirm(
            {"password": "new-password", "username": "cannot-change-this-account"}
        )
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data["username"] == "student"
    assert entry.data["password"] == "new-password"
    reload.assert_called_once_with(entry.entry_id)
