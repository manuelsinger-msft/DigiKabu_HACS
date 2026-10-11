"""Persistent change detection with invented student data."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from homeassistant.exceptions import HomeAssistantError

from custom_components.digikabu.api import (
    DigiKabuConnectionError,
    DigiKabuResponseError,
)
from custom_components.digikabu.timetable import week_start
from custom_components.digikabu.timetable_cache import TimetableCache

START = datetime.fromisoformat("2026-10-12T00:00:00+02:00")


def lesson(**overrides):
    return {
        "datum": "12.10.2026",
        "anfStd": 2,
        "endStd": 3,
        "uFachBez": "Testfach",
        "lehrer": "TEST",
        "raumLongtext": "R0",
        "gruppe": "1/1",
        **overrides,
    }


async def fetch(cache, client, items, start=START, weeks=1, group=None):
    client.async_get_timetable.return_value = items
    with patch(
        "custom_components.digikabu.timetable_cache.dt_util.utcnow",
        return_value=datetime.fromisoformat("2026-10-11T12:00:00+00:00"),
    ):
        return await cache.async_get_weeks(client, start, weeks, group)


async def test_first_nonempty_day_is_baseline(hass, mock_api):
    cache = TimetableCache(hass, "account")
    await fetch(cache, mock_api, [])
    assert cache.data == {}
    result = await fetch(cache, mock_api, [lesson()])
    assert "Geaendert" not in str(result)
    assert result[0]["rows"][1]["cell_styles"] == [None] * 5
    await fetch(cache, mock_api, [lesson(), lesson(datum="13.10.2026")])
    assert cache.data["2026-10-13"]["2|1/1"]["status"] == ""


async def test_change_persists_across_same_reads_and_restart(hass, mock_api):
    cache = TimetableCache(hass, "account")
    await fetch(cache, mock_api, [lesson()])
    changed = [lesson(lehrer="NEW")]
    result = await fetch(cache, mock_api, changed)
    rows = result[0]["rows"]
    assert "Geaendert seit vorherigem Abruf" in rows[1]["cells"][0]
    assert rows[1]["cell_styles"][0]["bg"] == "#f9a825"
    assert rows[2]["break"] is True
    assert rows[3]["cell_styles"][0]["bg"] == "#f9a825"
    assert await fetch(cache, mock_api, changed) == result
    restored = TimetableCache(hass, "account")
    with patch(
        "custom_components.digikabu.timetable_cache.dt_util.utcnow",
        return_value=datetime.fromisoformat("2026-10-11T12:00:00+00:00"),
    ):
        await restored.async_load()
    assert await fetch(restored, mock_api, changed) == result


async def test_cancelled_tombstone_persists_and_reappearance_changes(hass, mock_api):
    cache = TimetableCache(hass, "account")
    await fetch(cache, mock_api, [lesson()])
    result = await fetch(cache, mock_api, [])
    row = result[0]["rows"][1]
    assert "Testfach" in row["cells"][0]
    assert "Entfallen seit vorherigem Abruf" in row["cells"][0]
    assert row["cell_styles"][0]["bg"] == "#d32f2f"
    assert await fetch(cache, mock_api, []) == result
    returned = await fetch(cache, mock_api, [lesson()])
    assert "Entfallen" not in str(returned)
    assert "Geaendert" in str(returned)


async def test_partial_range_cancel_and_new_slot(hass, mock_api):
    cache = TimetableCache(hass, "account")
    await fetch(cache, mock_api, [lesson()])
    result = await fetch(
        cache,
        mock_api,
        [lesson(endStd=2), lesson(anfStd=4, endStd=4, uFachBez="Extra")],
    )
    rows = result[0]["rows"]
    assert "Geaendert" not in rows[1]["cells"][0]
    assert "Entfallen" in rows[3]["cells"][0]
    assert "Geaendert" in rows[4]["cells"][0]


async def test_parallel_groups_and_filter_do_not_change_baseline(hass, mock_api):
    cache = TimetableCache(hass, "account")
    entries = [lesson(gruppe="1/2"), lesson(gruppe="2/2")]
    await fetch(cache, mock_api, entries, group="1/2")
    result = await fetch(cache, mock_api, entries, group="2/2")
    assert "Geaendert" not in str(result)
    assert "Entfallen" not in str(result)
    changed = [lesson(gruppe="1/2", raumLongtext="R1")]
    result = await fetch(cache, mock_api, changed)
    text = result[0]["rows"][1]["cells"][0]
    assert "Geaendert" in text
    assert "Entfallen" in text
    assert result[0]["rows"][1]["cell_styles"][0]["bg"] == "#f9a825"


async def test_subset_weeks_do_not_cancel_unrequested_days(hass, mock_api):
    cache = TimetableCache(hass, "account")
    await fetch(cache, mock_api, [lesson(), lesson(datum="19.10.2026")], weeks=2)
    await fetch(cache, mock_api, [lesson()], weeks=1)
    assert cache.data["2026-10-19"]["2|1/1"]["status"] == ""


async def test_prune_exact_school_date_window(hass, mock_api):
    cache = TimetableCache(hass, "account")
    today = START.date() - timedelta(days=1)
    cache.data = {
        (today + timedelta(days=offset)).isoformat(): {
            "1|": {"labels": ["Test"], "status": "changed"}
        }
        for offset in range(-10, 23)
    }
    await fetch(cache, mock_api, [])
    assert min(cache.data) == "2026-10-04"
    assert max(cache.data) == "2026-10-30"
    assert len(cache.data) == 27
    with patch(
        "custom_components.digikabu.timetable_cache.dt_util.utcnow",
        return_value=datetime.fromisoformat("2026-10-12T00:01:00+02:00"),
    ):
        restored = TimetableCache(hass, "account")
        await restored.async_load()
    assert min(restored.data) == "2026-10-05"


async def test_failed_request_does_not_cancel_lessons(hass, mock_api):
    cache = TimetableCache(hass, "account")
    await fetch(cache, mock_api, [lesson()])
    before = dict(cache.data)
    mock_api.async_get_timetable.side_effect = DigiKabuConnectionError("offline")
    with pytest.raises(DigiKabuConnectionError):
        await fetch(cache, mock_api, [])
    assert cache.data == before


async def test_failed_storage_does_not_advance_baseline(hass, mock_api):
    cache = TimetableCache(hass, "account")
    await fetch(cache, mock_api, [lesson()])
    before = dict(cache.data)
    with (
        patch.object(cache.store, "async_save", side_effect=OSError("disk error")),
        pytest.raises(OSError),
    ):
        await fetch(cache, mock_api, [lesson(lehrer="NEW")])
    assert cache.data == before


async def test_invalid_response_does_not_advance_baseline(hass, mock_api):
    cache = TimetableCache(hass, "account")
    await fetch(cache, mock_api, [lesson()])
    before = dict(cache.data)
    with pytest.raises(DigiKabuResponseError):
        await fetch(cache, mock_api, [lesson(), lesson(anfStd=11)])
    assert cache.data == before


async def test_reordered_entries_are_not_changes(hass, mock_api):
    cache = TimetableCache(hass, "account")
    entries = [lesson(), lesson(uFachBez="Parallel")]
    first = await fetch(cache, mock_api, entries)
    assert await fetch(cache, mock_api, list(reversed(entries))) == first


async def test_cache_removal_is_account_scoped(hass, mock_api):
    first, second = TimetableCache(hass, "one"), TimetableCache(hass, "two")
    await fetch(first, mock_api, [lesson()])
    await fetch(second, mock_api, [lesson()])
    await first.async_remove()
    assert await first.store.async_load() is None
    assert await second.store.async_load() is not None


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"bad-date": {}},
        {"2026-10-12": []},
        {"2026-10-12": {"1|": {"labels": [], "status": ""}}},
        {"2026-10-12": {"11|": {"labels": ["Test"], "status": ""}}},
        {"2026-10-12": {"1|": {"labels": ["Test"], "status": "unknown"}}},
        {"2026-10-12": {1: {"labels": ["Test"], "status": ""}}},
    ],
)
async def test_invalid_cache_fails_explicitly(hass, data):
    cache = TimetableCache(hass, "account")
    with (
        patch.object(cache.store, "async_load", return_value=data),
        pytest.raises(HomeAssistantError),
    ):
        await cache.async_load()


async def test_concurrent_fetches_keep_order(hass, mock_api):
    cache = TimetableCache(hass, "account")
    mock_api.async_get_timetable.side_effect = [
        [lesson()],
        [lesson(lehrer="NEW")],
        [lesson(lehrer="NEW")],
    ]
    with patch(
        "custom_components.digikabu.timetable_cache.dt_util.utcnow",
        return_value=datetime.fromisoformat("2026-10-11T12:00:00+00:00"),
    ):
        results = await asyncio.gather(
            *(
                cache.async_get_weeks(mock_api, week_start(START), 1, None)
                for _ in range(3)
            )
        )
    assert "Geaendert" not in str(results[0])
    assert "Geaendert" in str(results[1])
    assert results[1] == results[2]
