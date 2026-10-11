"""Convert the observed student timetable format to stundenplan-card rows."""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from homeassistant.util import dt as dt_util

from .api import DigiKabuResponseError, JSONValue

SCHOOL_TIMEZONE = ZoneInfo("Europe/Berlin")
DAYS = ["Mo", "Di", "Mi", "Do", "Fr"]
LESSON_TIMES = (
    ("08:30", "09:15"),
    ("09:15", "10:00"),
    ("10:15", "11:00"),
    ("11:00", "11:45"),
    ("11:45", "12:30"),
    ("12:30", "13:15"),
    ("13:15", "14:00"),
    ("14:00", "14:45"),
    ("14:45", "15:30"),
    ("15:30", "16:15"),
)


def week_start(datum: datetime | None) -> datetime:
    """Use Monday of the requested week, in school-local time."""
    value = datum or dt_util.utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=SCHOOL_TIMEZONE)
    day = value.astimezone(SCHOOL_TIMEZONE).date()
    return datetime.combine(
        day - timedelta(days=day.weekday()), time.min, SCHOOL_TIMEZONE
    )


def _text(item: dict[str, JSONValue], key: str, index: int) -> str:
    value = item.get(key)
    if value is None:
        return ""
    if not isinstance(value, str):
        raise DigiKabuResponseError(
            f"Timetable entry {index}: {key} must be text or null"
        )
    return value.strip()


type TimetableSlots = dict[date, dict[str, list[str]]]


def parse_timetable(response: JSONValue, start: date, weeks: int) -> TimetableSlots:
    """Keep groups independent and split ranges into comparable lesson slots."""
    if not isinstance(response, list):
        raise DigiKabuResponseError("The card timetable requires a JSON list")
    slots: TimetableSlots = {}
    for index, item in enumerate(response):
        if not isinstance(item, dict):
            raise DigiKabuResponseError(f"Timetable entry {index} must be an object")
        raw_date = _text(item, "datum", index)
        try:
            day = datetime.strptime(raw_date, "%d.%m.%Y").date()
        except ValueError as err:
            raise DigiKabuResponseError(
                f"Timetable entry {index}: datum must use DD.MM.YYYY"
            ) from err
        if not start <= day < start + timedelta(days=7 * weeks):
            raise DigiKabuResponseError(
                f"Timetable entry {index} is outside the requested weeks"
            )
        first, last = item.get("anfStd"), item.get("endStd")
        if (
            type(first) is not int
            or type(last) is not int
            or not 1 <= first <= last <= len(LESSON_TIMES)
        ):
            raise DigiKabuResponseError(
                f"Timetable entry {index}: lesson range must be between 1 and 10"
            )
        subject = _text(item, "uFachBez", index)
        if not subject:
            raise DigiKabuResponseError(
                f"Timetable entry {index}: uFachBez must not be empty"
            )
        teacher = _text(item, "lehrer", index)
        room = _text(item, "raumLongtext", index)
        group = _text(item, "gruppe", index)
        if day.weekday() > 4:
            continue
        details = " / ".join(value for value in (teacher, room, group) if value)
        label = subject + (f"\n{details}" if details else "")
        for lesson in range(first, last + 1):
            labels = slots.setdefault(day, {}).setdefault(f"{lesson}|{group}", [])
            if label not in labels:
                labels.append(label)
                labels.sort()
    return slots


def prepare_card_weeks(
    response: JSONValue, start: date, weeks: int, gruppe: str | None = None
) -> list[dict[str, JSONValue]]:
    """Render an unmarked baseline without a stored previous observation."""
    slots = parse_timetable(response, start, weeks)
    return render_card_weeks(slots, {}, start, weeks, gruppe)


def render_card_weeks(
    slots: TimetableSlots,
    statuses: dict[date, dict[str, str]],
    start: date,
    weeks: int,
    gruppe: str | None = None,
) -> list[dict[str, JSONValue]]:
    """Text identifies each changed group even when a cell mixes statuses."""
    cells: dict[tuple[date, int], list[str]] = {}
    cell_statuses: dict[tuple[date, int], list[str]] = {}
    for day, entries in slots.items():
        for key, labels in sorted(entries.items()):
            number, group = key.split("|", 1)
            if gruppe and group not in ("", "1/1", gruppe):
                continue
            status = statuses.get(day, {}).get(key, "")
            suffix = {
                "changed": "\nGeaendert seit vorherigem Abruf",
                "cancelled": "\nEntfallen seit vorherigem Abruf",
            }.get(status, "")
            cell = (day, int(number))
            cells.setdefault(cell, []).extend(label + suffix for label in labels)
            cell_statuses.setdefault(cell, []).append(status)

    result: list[dict[str, JSONValue]] = []
    for offset in range(weeks):
        monday = start + timedelta(weeks=offset)
        dates = [monday + timedelta(days=day) for day in range(5)]
        rows: list[JSONValue] = []
        for lesson, (begin, end) in enumerate(LESSON_TIMES, 1):
            if lesson == 3:
                rows.append({"break": True, "time": "10:00 - 10:15", "label": "Pause"})
            rows.append(
                {
                    "time": f"{begin} - {end}",
                    "start": begin,
                    "end": end,
                    "cells": [
                        "\n\n".join(cells.get((day, lesson), ())) for day in dates
                    ],
                    "cell_styles": [
                        (
                            {"bg": "#d32f2f", "color": "#ffffff"}
                            if cell_statuses.get((day, lesson))
                            and all(
                                status == "cancelled"
                                for status in cell_statuses[(day, lesson)]
                            )
                            else {"bg": "#f9a825", "color": "#000000"}
                            if any(cell_statuses.get((day, lesson), ()))
                            else None
                        )
                        for day in dates
                    ],
                }
            )
        result.append(
            {
                "week_start": monday.isoformat(),
                "week_end": dates[-1].isoformat(),
                "dates": [day.isoformat() for day in dates],
                "days": list(DAYS),
                "rows": rows,
            }
        )
    return result
