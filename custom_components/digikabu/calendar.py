"""Read-only calendars for the observed student exam and appointment formats."""

import asyncio
import logging
from datetime import date, datetime, time, timedelta

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .api import DigiKabuAuthError, DigiKabuError, DigiKabuResponseError, JSONValue
from .const import BASE_URL, DOMAIN, UPDATE_INTERVAL
from .coordinator import DigiKabuConfigEntry, DigiKabuCoordinator
from .timetable import SCHOOL_TIMEZONE

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0


def parse_events(response: JSONValue, endpoint: str) -> list[CalendarEvent]:
    """Reject unknown shapes rather than publishing invented or partial events."""
    if not isinstance(response, list):
        raise DigiKabuResponseError("Calendar response must be a list")
    events: list[CalendarEvent] = []
    for index, item in enumerate(response):
        if not isinstance(item, dict):
            raise DigiKabuResponseError(f"Calendar entry {index} must be an object")
        title = item.get("info" if endpoint == "exams" else "hinweis")
        if not isinstance(title, str) or not title.strip():
            raise DigiKabuResponseError(f"Calendar entry {index} needs a title")
        try:
            if endpoint == "exams":
                raw = item.get("date")
                if not isinstance(raw, str):
                    raise ValueError("Missing date")
                start = datetime.strptime(raw, "%d.%m.%Y").date()
                end = start + timedelta(days=1)
            else:
                raw_start, raw_end = item.get("datumVon"), item.get("datumBis")
                if not isinstance(raw_start, str) or not isinstance(raw_end, str):
                    raise ValueError("Missing date range")
                first, last = (
                    datetime.fromisoformat(raw_start),
                    datetime.fromisoformat(raw_end),
                )
                if first.tzinfo:
                    first = first.astimezone(SCHOOL_TIMEZONE)
                if last.tzinfo:
                    last = last.astimezone(SCHOOL_TIMEZONE)
                if first.time() != time.min or last.time() != time.min:
                    raise ValueError("Only the observed all-day format is supported")
                if first.date() != last.date():
                    raise ValueError("Multi-day end semantics are undocumented")
                start = first.date()
                end = start + timedelta(days=1)
        except (ValueError, OverflowError) as err:
            raise DigiKabuResponseError(
                f"Calendar entry {index} has an unsupported date range"
            ) from err
        events.append(CalendarEvent(start=start, end=end, summary=title.strip()))
    return sorted(events, key=lambda event: (event.start, event.summary))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: DigiKabuConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities(
        DigiKabuCalendar(entry, entry.runtime_data.coordinators[endpoint])
        for endpoint in ("exams", "appointments")
    )


class DigiKabuCalendar(CoordinatorEntity[DigiKabuCoordinator], CalendarEntity):
    """Share current-month polling; fetch other exam months only on demand."""

    _attr_has_entity_name = True
    _attr_supported_features = 0

    def __init__(
        self, entry: DigiKabuConfigEntry, coordinator: DigiKabuCoordinator
    ) -> None:
        super().__init__(coordinator)
        self.entry = entry
        self._attr_unique_id = f"{entry.entry_id}_calendar_{coordinator.endpoint}"
        self._attr_translation_key = coordinator.endpoint
        self._attr_initial_color = (
            "#f3c45e" if coordinator.endpoint == "exams" else "#62c9f3"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="DigiKabu",
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=BASE_URL,
        )
        self._events: list[CalendarEvent] = []
        self._valid = False
        self._months: dict[int, tuple[datetime, list[CalendarEvent]]] = {}
        self._lock = asyncio.Lock()
        self._convert_current()

    def _convert_current(self) -> None:
        if self.coordinator.data is None:
            self._valid = False
            return
        try:
            self._events = parse_events(
                self.coordinator.data.response, self.coordinator.endpoint
            )
        except DigiKabuResponseError as err:
            self._valid = False
            _LOGGER.error("DigiKabu %s calendar: %s", self.coordinator.endpoint, err)
        else:
            self._valid = True

    @callback
    def _handle_coordinator_update(self) -> None:
        self._convert_current()
        super()._handle_coordinator_update()
        self.async_update_event_listeners()

    @property
    def available(self) -> bool:
        return super().available and self._valid

    @property
    def event(self) -> CalendarEvent | None:
        today = dt_util.now().date()
        return next((event for event in self._events if event.end > today), None)

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        if not self.available:
            raise HomeAssistantError("DigiKabu calendar data is unavailable")
        if self.coordinator.endpoint == "appointments":
            events = self._events
        else:
            months: set[int] = set()
            day = start_date.date()
            last = (end_date - timedelta(microseconds=1)).date()
            while day <= last and len(months) < 12:
                months.add(day.month)
                day = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
            events = []
            async with self._lock:
                for month in sorted(months):
                    now = dt_util.utcnow()
                    if month == now.astimezone(SCHOOL_TIMEZONE).month:
                        events.extend(self._events)
                        continue
                    cached = self._months.get(month)
                    if cached is None or now - cached[0] >= UPDATE_INTERVAL:
                        try:
                            response = (
                                await self.entry.runtime_data.client.async_get_exams(
                                    month
                                )
                            )
                            parsed = parse_events(response, "exams")
                        except DigiKabuAuthError as err:
                            self.entry.async_start_reauth(hass)
                            raise HomeAssistantError(
                                "DigiKabu calendar authentication failed"
                            ) from err
                        except DigiKabuError as err:
                            raise HomeAssistantError(str(err)) from err
                        cached = (now, parsed)
                        self._months[month] = cached
                    events.extend(cached[1])

        def local_midnight(value: date) -> datetime:
            return datetime.combine(value, time.min, start_date.tzinfo)

        return sorted(
            [
                event
                for event in events
                if local_midnight(event.end) > start_date
                and local_midnight(event.start) < end_date
            ],
            key=lambda event: (event.start, event.summary),
        )
