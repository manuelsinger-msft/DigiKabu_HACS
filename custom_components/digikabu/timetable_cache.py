"""Account-local, bounded observations; not official substitution statuses."""

import asyncio
from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import TypedDict

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .api import DigiKabuApi, JSONValue
from .timetable import SCHOOL_TIMEZONE, parse_timetable, render_card_weeks


class SlotRecord(TypedDict):
    labels: list[str]
    status: str


type CacheData = dict[str, dict[str, SlotRecord]]


class TimetableCache:
    """Serialize fetch/compare/save so concurrent requests cannot reorder history."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self.store = Store[CacheData](
            hass,
            1,
            f"digikabu.{entry_id}.timetable",
            private=True,
            atomic_writes=True,
        )
        self.data: CacheData = {}
        self.lock = asyncio.Lock()

    def _prune(self, data: CacheData) -> CacheData:
        today = dt_util.utcnow().astimezone(SCHOOL_TIMEZONE).date()
        first, last = today - timedelta(days=7), today + timedelta(days=19)
        return {
            day: entries
            for day, entries in data.items()
            if first <= date.fromisoformat(day) <= last
        }

    async def async_load(self) -> None:
        loaded = await self.store.async_load()
        if loaded is None:
            return
        if not isinstance(loaded, dict):
            raise HomeAssistantError("Invalid DigiKabu timetable cache")
        for day, entries in loaded.items():
            try:
                date.fromisoformat(day)
            except (ValueError, TypeError) as err:
                raise HomeAssistantError("Invalid DigiKabu cache date") from err
            if not isinstance(entries, dict):
                raise HomeAssistantError("Invalid DigiKabu cache day")
            for key, record in entries.items():
                if not isinstance(key, str):
                    raise HomeAssistantError("Invalid DigiKabu cache lesson key")
                parts = key.split("|", 1)
                if (
                    len(parts) != 2
                    or parts[0] not in {str(n) for n in range(1, 11)}
                    or not isinstance(record, dict)
                    or record.get("status") not in ("", "changed", "cancelled")
                    or not isinstance(record.get("labels"), list)
                    or not record["labels"]
                    or not all(isinstance(label, str) for label in record["labels"])
                ):
                    raise HomeAssistantError("Invalid DigiKabu cache lesson")
        self.data = self._prune(loaded)
        await self.store.async_save(self.data)

    async def async_get_weeks(
        self, client: DigiKabuApi, start: datetime, weeks: int, gruppe: str | None
    ) -> list[dict[str, JSONValue]]:
        async with self.lock:
            raw = await client.async_get_timetable(start, 7 * (weeks - 1) + 5)
            incoming = parse_timetable(raw, start.date(), weeks)
            updated = deepcopy(self._prune(self.data))
            for offset in range(7 * (weeks - 1) + 5):
                day = start.date() + timedelta(days=offset)
                if day.weekday() > 4:
                    continue
                current = incoming.get(day, {})
                previous = updated.get(day.isoformat(), {})
                if not previous and not current:
                    continue
                merged: dict[str, SlotRecord] = {}
                for key in previous.keys() | current.keys():
                    old = previous.get(key)
                    labels = current.get(key)
                    if labels is None:
                        if old is not None:
                            merged[key] = {
                                "labels": old["labels"],
                                "status": "cancelled",
                            }
                    else:
                        changed = bool(previous) and (
                            old is None
                            or old["labels"] != labels
                            or old["status"] == "cancelled"
                        )
                        merged[key] = {
                            "labels": labels,
                            "status": "changed"
                            if changed
                            else old["status"]
                            if old
                            else "",
                        }
                updated[day.isoformat()] = merged
            slots = {
                date.fromisoformat(day): {
                    key: record["labels"] for key, record in entries.items()
                }
                for day, entries in updated.items()
            }
            statuses = {
                date.fromisoformat(day): {
                    key: record["status"] for key, record in entries.items()
                }
                for day, entries in updated.items()
            }
            result = render_card_weeks(slots, statuses, start.date(), weeks, gruppe)
            bounded = self._prune(updated)
            await self.store.async_save(bounded)
            self.data = bounded
            return result

    async def async_remove(self) -> None:
        await self.store.async_remove()
