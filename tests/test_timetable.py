"""Card rows from invented data, never from a student's real timetable."""

from datetime import date, datetime
from unittest.mock import patch

import pytest

from custom_components.digikabu.api import DigiKabuResponseError
from custom_components.digikabu.timetable import prepare_card_weeks, week_start


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


def test_rows_split_double_lesson_at_break():
    original = [lesson()]
    weeks = prepare_card_weeks(original, date(2026, 10, 12), 1)
    week = weeks[0]
    assert week["dates"] == [
        "2026-10-12",
        "2026-10-13",
        "2026-10-14",
        "2026-10-15",
        "2026-10-16",
    ]
    assert week["days"] == ["Mo", "Di", "Mi", "Do", "Fr"]
    rows = week["rows"]
    assert len(rows) == 11
    assert rows[1]["time"] == "09:15 - 10:00"
    assert rows[2] == {"break": True, "time": "10:00 - 10:15", "label": "Pause"}
    assert rows[3]["time"] == "10:15 - 11:00"
    assert (
        rows[1]["cells"]
        == rows[3]["cells"]
        == ["Testfach\nTEST / R0 / 1/1", "", "", "", ""]
    )
    assert rows[0]["cells"] == [""] * 5
    assert original == [lesson()]


def test_two_weeks_and_parallel_groups():
    entries = [
        lesson(uFachBez="Parallel A", gruppe="1/2"),
        lesson(uFachBez="Parallel B", gruppe="2/2"),
        lesson(datum="19.10.2026", uFachBez="Woche zwei"),
    ]
    weeks = prepare_card_weeks(entries, date(2026, 10, 12), 2)
    assert weeks[1]["week_start"] == "2026-10-19"
    assert weeks[1]["week_end"] == "2026-10-23"
    assert "Parallel A" in weeks[0]["rows"][1]["cells"][0]
    assert "Parallel B" in weeks[0]["rows"][1]["cells"][0]
    assert "Woche zwei" in weeks[1]["rows"][1]["cells"][0]


def test_filter_keeps_shared_lessons_and_deduplicates():
    entries = [
        lesson(),
        lesson(),
        lesson(uFachBez="A", gruppe="1/2"),
        lesson(uFachBez="B", gruppe="2/2"),
        lesson(datum="17.10.2026", uFachBez="Weekend"),
    ]
    rows = prepare_card_weeks(entries, date(2026, 10, 12), 1, "1/2")[0]["rows"]
    assert rows[1]["cells"][0].count("Testfach") == 1
    assert "A\n" in rows[1]["cells"][0]
    assert "B\n" not in rows[1]["cells"][0]
    assert "Weekend" not in str(rows)


def test_empty_weeks_have_full_grid():
    weeks = prepare_card_weeks([], date(2026, 10, 12), 2)
    assert len(weeks) == 2
    for week in weeks:
        assert len(week["rows"]) == 11
        for row in week["rows"]:
            if not row.get("break"):
                assert row["cells"] == [""] * 5


@pytest.mark.parametrize(
    "response",
    [
        None,
        {},
        "invalid",
        [None],
        [lesson(datum="2026-10-12")],
        [lesson(datum="31.02.2026")],
        [lesson(datum="26.10.2026")],
        [lesson(anfStd=True)],
        [lesson(endStd=3.5)],
        [lesson(anfStd=0)],
        [lesson(endStd=11)],
        [lesson(anfStd=4)],
        [lesson(uFachBez=None)],
        [lesson(lehrer=123)],
    ],
)
def test_unsupported_data_is_explicit_error(response):
    with pytest.raises(DigiKabuResponseError):
        prepare_card_weeks(response, date(2026, 10, 12), 2)


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        ("2026-10-14T12:00:00", "2026-10-12T00:00:00+02:00"),
        ("2026-10-26T00:30:00+02:00", "2026-10-19T00:00:00+02:00"),
        ("2026-10-27T12:00:00+00:00", "2026-10-26T00:00:00+01:00"),
    ],
)
def test_school_week_and_dst(requested, expected):
    assert week_start(datetime.fromisoformat(requested)).isoformat() == expected


def test_default_current_week():
    with patch(
        "custom_components.digikabu.timetable.dt_util.utcnow",
        return_value=datetime.fromisoformat("2026-10-14T12:00:00+00:00"),
    ):
        assert week_start(None).date() == date(2026, 10, 12)
