from datetime import date

from src.ingest import month_starts


def test_month_starts_crosses_year_and_stops_before_end():
    assert month_starts(date(2025, 11, 15), date(2026, 2, 1)) == [
        date(2025, 11, 1),
        date(2025, 12, 1),
        date(2026, 1, 1),
    ]


def test_month_starts_includes_partial_last_month():
    assert month_starts(date(2026, 11, 1), date(2026, 11, 19)) == [date(2026, 11, 1)]
