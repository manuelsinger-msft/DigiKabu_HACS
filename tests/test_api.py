"""Contract tests: synthetic data, no DigiKabu credentials or live writes."""

import asyncio
import json
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from aiohttp import ClientResponse, ClientSession
from aioresponses import aioresponses as _aioresponses
from yarl import URL

from custom_components.digikabu.api import (
    DigiKabuApi,
    DigiKabuAuthError,
    DigiKabuConnectionError,
    DigiKabuError,
    DigiKabuResponseError,
)
from custom_components.digikabu.const import BASE_URL

TOKEN = "header.payload.signature"
AUTH = f"{BASE_URL}/api/authenticate"


class _Response(ClientResponse):
    """Supply aiohttp 3.14's new argument through aioresponses' public hook."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, stream_writer=Mock())


class aioresponses(_aioresponses):
    def add(self, *args, **kwargs):
        kwargs.setdefault("response_class", _Response)
        return super().add(*args, **kwargs)


@pytest.mark.parametrize("quoted", [True, False])
async def test_auth_token_formats(client, quoted):
    with aioresponses() as http:
        if quoted:
            http.post(AUTH, payload=TOKEN)
        else:
            http.post(AUTH, body=TOKEN, content_type="text/plain")
        await client.async_authenticate()
        request = next(iter(http.requests.values()))[0]
        assert request.kwargs["json"] == {
            "userName": "student",
            "password": "test-password",
        }
        assert "Authorization" not in request.kwargs["headers"]
        assert request.kwargs["allow_redirects"] is False
        assert request.kwargs["timeout"].total == 30


async def test_optional_key():
    async with ClientSession() as session:
        client = DigiKabuApi(session, "student", "password", "synthetic-key")
        with aioresponses() as http:
            http.post(f"{AUTH}?key=synthetic-key", payload=TOKEN)
            await client.async_authenticate()


@pytest.mark.parametrize("status", [400, 401, 403])
async def test_rejected_credentials(client, status):
    with aioresponses() as http:
        http.post(AUTH, status=status, body="secret response must never be shown")
        with pytest.raises(DigiKabuAuthError) as err:
            await client.async_authenticate()
        assert "secret" not in str(err.value)


@pytest.mark.parametrize(
    "body", ['{"token":"not-a-documented-model"}', '""', "<html>login</html>", ""]
)
async def test_unsupported_auth_response(client, body):
    with aioresponses() as http:
        http.post(AUTH, body=body)
        with pytest.raises(DigiKabuResponseError):
            await client.async_authenticate()


async def test_all_read_endpoints_and_params(client):
    datum = datetime(2026, 10, 12, tzinfo=UTC)
    payloads = [{"unknownFields": [1, None]}, [], "some data", None]
    urls = [
        f"{BASE_URL}/api/schueler/fehlzeiten",
        f"{BASE_URL}/api/stundenplan?anzahl=2&datum=2026-10-12T00%3A00%3A00%2B00%3A00",
        f"{BASE_URL}/api/termine/schulaufgaben?monat=11",
        f"{BASE_URL}/api/termine",
    ]
    with aioresponses() as http:
        http.post(AUTH, payload=TOKEN)
        for url, payload in zip(urls, payloads, strict=True):
            http.get(url, body=json.dumps(payload))
        assert await client.async_get_absences() == payloads[0]
        assert await client.async_get_timetable(datum, 2) == payloads[1]
        assert await client.async_get_exams(11) == payloads[2]
        assert await client.async_get_appointments() == payloads[3]
        for (method, _), requests in http.requests.items():
            if method == "GET":
                assert (
                    requests[0].kwargs["headers"]["Authorization"] == f"Bearer {TOKEN}"
                )


async def test_default_parameters_and_serialized_login(client):
    with aioresponses() as http:
        http.post(AUTH, payload=TOKEN)
        http.get(f"{BASE_URL}/api/stundenplan?anzahl=1", payload=[])
        http.get(f"{BASE_URL}/api/termine/schulaufgaben?monat=-1", payload=[])
        await asyncio.gather(client.async_get_timetable(), client.async_get_exams())
        assert len(http.requests[("POST", URL(AUTH))]) == 1


async def test_token_renewal_once(client):
    url = f"{BASE_URL}/api/schueler/fehlzeiten"
    with aioresponses() as http:
        http.post(AUTH, payload=TOKEN)
        http.get(url, status=401)
        http.post(AUTH, payload="new.payload.signature")
        http.get(url, payload={"data": "preserved"})
        assert await client.async_get_absences() == {"data": "preserved"}
        requests = http.requests[("GET", URL(url))]
        assert requests[-1].kwargs["headers"]["Authorization"] == (
            "Bearer new.payload.signature"
        )


async def test_second_401_stops(client):
    url = f"{BASE_URL}/api/schueler/fehlzeiten"
    with aioresponses() as http:
        http.post(AUTH, payload=TOKEN)
        http.get(url, status=401)
        http.post(AUTH, payload=TOKEN)
        http.get(url, status=401)
        with pytest.raises(DigiKabuAuthError):
            await client.async_get_absences()
        assert len(http.requests[("POST", URL(AUTH))]) == 2


@pytest.mark.parametrize("status", [403, 429, 500, 302])
async def test_data_errors_are_not_auth_retry(client, status):
    with aioresponses() as http:
        http.post(AUTH, payload=TOKEN)
        http.get(
            f"{BASE_URL}/api/schueler/fehlzeiten", status=status, body="private data"
        )
        with pytest.raises(DigiKabuError) as err:
            await client.async_get_absences()
        assert str(status) in str(err.value)
        assert "private data" not in str(err.value)
        assert len(http.requests[("POST", URL(AUTH))]) == 1


async def test_bad_read_json(client):
    with aioresponses() as http:
        http.post(AUTH, payload=TOKEN)
        http.get(f"{BASE_URL}/api/schueler/fehlzeiten", body="<html>error</html>")
        with pytest.raises(DigiKabuResponseError):
            await client.async_get_absences()


async def test_write_payloads_and_empty_success(client):
    datum = datetime(2026, 10, 12, tzinfo=UTC)
    with aioresponses() as http:
        http.post(AUTH, payload=TOKEN)
        http.put(f"{BASE_URL}/api/schueler/entschuldigung", status=204)
        http.post(f"{BASE_URL}/api/settings/email", body="OK")
        await client.async_submit_excuse(datum, 3, "synthetic")
        await client.async_set_email("test@example.invalid", None)
        requests = [
            req[0].kwargs["json"]
            for (method, url), req in http.requests.items()
            if url.path != "/api/authenticate"
        ]
        assert requests == [
            {"abDatum": datum.isoformat(), "dauer": 3, "grund": "synthetic"},
            {"eMail1": "test@example.invalid", "eMail2": None},
        ]


async def test_write_timeout_never_replayed(client):
    url = f"{BASE_URL}/api/settings/email"
    with aioresponses() as http:
        http.post(AUTH, payload=TOKEN)
        http.post(url, exception=TimeoutError())
        with pytest.raises(DigiKabuConnectionError, match="outcome is unknown"):
            await client.async_set_email(None, None)
        assert len(http.requests[("POST", URL(url))]) == 1


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
async def test_invalid_timetable_days(client, value):
    with pytest.raises(ValueError):
        await client.async_get_timetable(anzahl=value)


@pytest.mark.parametrize("value", [0, -2, 13, True])
async def test_invalid_month(client, value):
    with pytest.raises(ValueError):
        await client.async_get_exams(value)


@pytest.mark.parametrize("value", [0, 4, True, 1.5])
async def test_invalid_excuse_duration(client, value):
    with pytest.raises(ValueError):
        await client.async_submit_excuse(datetime.now(UTC), value)
