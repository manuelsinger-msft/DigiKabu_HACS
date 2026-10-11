"""Asynchronous client for the documented DigiKabu student API."""

import asyncio
import json
import re
from datetime import datetime

from aiohttp import ClientError, ClientSession, ClientTimeout

from .const import BASE_URL, ENDPOINTS, REQUEST_TIMEOUT

type JSONValue = (
    dict[str, JSONValue] | list[JSONValue] | str | int | float | bool | None
)
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


class DigiKabuError(Exception):
    """An API failure with a safe, payload-free error message."""


class DigiKabuAuthError(DigiKabuError):
    """Credentials or a renewed token were rejected."""


class DigiKabuConnectionError(DigiKabuError):
    """The API could not be reached."""


class DigiKabuResponseError(DigiKabuError):
    """The API returned an unsupported response."""


class DigiKabuApi:
    """Reuse HA's session; keep credentials and the token out of logs and states."""

    def __init__(
        self,
        session: ClientSession,
        username: str,
        password: str,
        api_key: str = "",
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        self._api_key = api_key
        self._token: str | None = None
        self._lock = asyncio.Lock()

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
        data: dict[str, JSONValue] | None = None,
        authenticated: bool = True,
        write: bool = False,
    ) -> JSONValue:
        headers = {"Accept": "application/json"}
        if authenticated:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            async with self._session.request(
                method,
                f"{BASE_URL}{path}",
                params=params,
                json=data,
                headers=headers,
                timeout=ClientTimeout(total=REQUEST_TIMEOUT),
                allow_redirects=False,
            ) as response:
                if response.status == 401 or (
                    not authenticated and response.status in (400, 403)
                ):
                    raise DigiKabuAuthError("DigiKabu rejected authentication")
                if not 200 <= response.status < 300:
                    raise DigiKabuError(
                        f"DigiKabu returned HTTP {response.status} for {path}"
                    )
                text = await response.text()
        except ClientError, TimeoutError:
            message = (
                "DigiKabu write outcome is unknown; check DigiKabu before retrying"
                if write
                else "Cannot connect to DigiKabu"
            )
            # Transport exception URLs can contain the optional API key.
            raise DigiKabuConnectionError(message) from None
        except UnicodeError:
            raise DigiKabuResponseError(
                f"DigiKabu returned an unsupported encoding for {path}"
            ) from None

        if write:
            # Swagger defines no write response body. The successful status is enough.
            return None
        try:
            return json.loads(text)
        except (ValueError, RecursionError) as err:
            if not authenticated and _TOKEN_PATTERN.fullmatch(text.strip()):
                return text.strip()
            raise DigiKabuResponseError(
                f"DigiKabu returned an unsupported response for {path}"
            ) from err

    async def _authenticate(self) -> None:
        result = await self._request(
            "POST",
            "/api/authenticate",
            params={"key": self._api_key} if self._api_key else None,
            data={"userName": self._username, "password": self._password},
            authenticated=False,
        )
        if not isinstance(result, str) or not _TOKEN_PATTERN.fullmatch(result):
            raise DigiKabuResponseError(
                "Expected a JWT string from DigiKabu authentication"
            )
        self._token = result

    async def async_authenticate(self) -> None:
        """Obtain a token without persisting it to HA."""
        async with self._lock:
            await self._authenticate()

    async def _authenticated_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
        data: dict[str, JSONValue] | None = None,
        write: bool = False,
    ) -> JSONValue:
        async with self._lock:
            if self._token is None:
                await self._authenticate()
            try:
                return await self._request(
                    method, path, params=params, data=data, write=write
                )
            except DigiKabuAuthError:
                self._token = None
                await self._authenticate()
                # Only an explicit 401 is replayed, never a timeout or server error.
                try:
                    return await self._request(
                        method, path, params=params, data=data, write=write
                    )
                except DigiKabuAuthError:
                    self._token = None
                    raise

    async def async_get_absences(self) -> JSONValue:
        """Read the authenticated student's absence overview."""
        return await self._authenticated_request("GET", ENDPOINTS["absences"])

    async def async_get_timetable(
        self, datum: datetime | None = None, anzahl: int = 1
    ) -> JSONValue:
        """Read only the authenticated user's timetable."""
        if type(anzahl) is not int or anzahl < 1:
            raise ValueError("anzahl must be a positive integer")
        params: dict[str, str | int] = {"anzahl": anzahl}
        if datum is not None:
            params["datum"] = datum.isoformat()
        return await self._authenticated_request(
            "GET", ENDPOINTS["timetable"], params=params
        )

    async def async_get_exams(self, monat: int = -1) -> JSONValue:
        """Read the logged-in student's exams."""
        if type(monat) is not int or (monat != -1 and not 1 <= monat <= 12):
            raise ValueError("monat must be -1 or a month from 1 to 12")
        return await self._authenticated_request(
            "GET", ENDPOINTS["exams"], params={"monat": monat}
        )

    async def async_get_appointments(self) -> JSONValue:
        """Read appointments; department selection is irrelevant for students."""
        return await self._authenticated_request("GET", ENDPOINTS["appointments"])

    async def async_submit_excuse(
        self, ab_datum: datetime, dauer: int, grund: str | None = None
    ) -> None:
        """Submit an explicitly requested excuse; HA validates school-local dates."""
        if type(dauer) is not int or not 1 <= dauer <= 3:
            raise ValueError("dauer must be between 1 and 3 days")
        await self._authenticated_request(
            "PUT",
            "/api/schueler/entschuldigung",
            data={"abDatum": ab_datum.isoformat(), "dauer": dauer, "grund": grund},
            write=True,
        )

    async def async_set_email(self, email1: str | None, email2: str | None) -> None:
        """Explicitly replace both email fields, including intentional nulls."""
        await self._authenticated_request(
            "POST",
            "/api/settings/email",
            data={"eMail1": email1, "eMail2": email2},
            write=True,
        )
