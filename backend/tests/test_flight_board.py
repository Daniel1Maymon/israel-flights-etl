"""
Tests for the Flight Board: Israel-timezone filtering, cutoff logic, sorting,
and combined filter scenarios.

_compute_date_window accepts an optional `now_il` parameter so tests never
need to mock the system clock — just pass the desired Israel-time datetime.
"""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.api.flight_board import _build_query, _compute_date_window
from app.models.flight import Flight

ISRAEL_TZ = ZoneInfo("Asia/Jerusalem")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flight(**kwargs) -> Flight:
    defaults = dict(
        flight_id="fb-default",
        airline_code="LY",
        flight_number="LY001",
        direction="D",
        location_en="London",
        location_he="לונדון",
        location_city_en="London",
        airline_name="El Al",
        terminal="3",
        status_en="On Time",
        status_he="בזמן",
    )
    defaults.update(kwargs)
    return Flight(**defaults)


# ---------------------------------------------------------------------------
# Unit tests: _compute_date_window
# ---------------------------------------------------------------------------

class TestComputeDateWindow:

    # ── Default window (no explicit dates) ──────────────────────────────────

    def test_default_from_is_one_hour_ago(self):
        now = datetime(2024, 6, 15, 14, 30, 0, tzinfo=ISRAEL_TZ)
        from_dt, _ = _compute_date_window(None, None, now_il=now)

        assert from_dt == datetime(2024, 6, 15, 13, 30, 0, tzinfo=ISRAEL_TZ)

    def test_default_to_is_end_of_today(self):
        now = datetime(2024, 6, 15, 14, 30, 0, tzinfo=ISRAEL_TZ)
        _, to_dt = _compute_date_window(None, None, now_il=now)

        assert to_dt.year == 2024
        assert to_dt.month == 6
        assert to_dt.day == 15
        assert to_dt.hour == 23
        assert to_dt.minute == 59
        assert to_dt.second == 59

    # ── Midnight edge case ──────────────────────────────────────────────────

    def test_midnight_cutoff_crosses_into_previous_day(self):
        """At 00:05 Israel time the 1-hour cutoff falls on the previous calendar day."""
        now = datetime(2024, 6, 15, 0, 5, 0, tzinfo=ISRAEL_TZ)
        from_dt, to_dt = _compute_date_window(None, None, now_il=now)

        # cutoff = 23:05 of June 14
        assert from_dt.day == 14
        assert from_dt.hour == 23
        assert from_dt.minute == 5

        # end-of-day is still June 15
        assert to_dt.day == 15
        assert to_dt.hour == 23

    def test_one_minute_past_midnight(self):
        now = datetime(2024, 3, 20, 0, 1, 0, tzinfo=ISRAEL_TZ)
        from_dt, _ = _compute_date_window(None, None, now_il=now)

        assert from_dt.day == 19       # previous day
        assert from_dt.hour == 23
        assert from_dt.minute == 1

    # ── One-hour cutoff behaviour ───────────────────────────────────────────

    def test_flight_90_min_ago_is_before_cutoff(self):
        now = datetime(2024, 6, 15, 14, 0, 0, tzinfo=ISRAEL_TZ)
        from_dt, _ = _compute_date_window(None, None, now_il=now)

        flight_time = now - timedelta(minutes=90)
        assert flight_time < from_dt, "Flight 90 min ago should be excluded by cutoff"

    def test_flight_30_min_ago_is_after_cutoff(self):
        now = datetime(2024, 6, 15, 14, 0, 0, tzinfo=ISRAEL_TZ)
        from_dt, _ = _compute_date_window(None, None, now_il=now)

        flight_time = now - timedelta(minutes=30)
        assert flight_time >= from_dt, "Flight 30 min ago should be included"

    def test_flight_exactly_one_hour_ago_is_at_boundary(self):
        now = datetime(2024, 6, 15, 14, 0, 0, tzinfo=ISRAEL_TZ)
        from_dt, _ = _compute_date_window(None, None, now_il=now)

        assert from_dt == now - timedelta(hours=1)

    # ── Explicit date overrides ─────────────────────────────────────────────

    def test_explicit_date_from_starts_at_midnight(self):
        from_dt, to_dt = _compute_date_window(date(2024, 3, 15), None)

        assert from_dt is not None
        assert from_dt.year == 2024
        assert from_dt.month == 3
        assert from_dt.day == 15
        assert from_dt.hour == 0
        assert from_dt.minute == 0
        assert to_dt is None

    def test_explicit_date_to_ends_at_23_59(self):
        from_dt, to_dt = _compute_date_window(None, date(2024, 3, 20))

        assert to_dt is not None
        assert to_dt.day == 20
        assert to_dt.hour == 23
        assert to_dt.minute == 59
        assert to_dt.second == 59
        assert from_dt is None

    def test_explicit_range_both_dates(self):
        from_dt, to_dt = _compute_date_window(date(2024, 1, 10), date(2024, 1, 15))

        assert from_dt.day == 10 and from_dt.hour == 0
        assert to_dt.day == 15 and to_dt.hour == 23

    def test_explicit_dates_use_israel_timezone(self):
        from_dt, to_dt = _compute_date_window(date(2024, 3, 15), date(2024, 3, 20))

        assert from_dt.tzinfo is not None
        assert to_dt.tzinfo is not None
        assert "Jerusalem" in str(from_dt.tzinfo)

    def test_explicit_dates_ignore_now_il(self):
        """now_il should have no effect when explicit dates are provided."""
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=ISRAEL_TZ)
        from_dt, to_dt = _compute_date_window(date(2024, 1, 1), date(2024, 1, 31), now_il=now)

        assert from_dt.month == 1 and from_dt.day == 1
        assert to_dt.month == 1 and to_dt.day == 31


# ---------------------------------------------------------------------------
# Integration tests: _build_query
# ---------------------------------------------------------------------------

class TestBuildQuery:
    """Tests that exercise the ORM query builder with an in-memory SQLite DB."""

    def _add_flights(self, db_session, flights):
        db_session.add_all(flights)
        db_session.commit()

    # ── Sorting ─────────────────────────────────────────────────────────────

    def test_sort_ascending_scheduled_time(self, db_session):
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=ISRAEL_TZ)
        self._add_flights(db_session, [
            _flight(flight_id="s3", flight_number="LY003", scheduled_time=now + timedelta(hours=3)),
            _flight(flight_id="s1", flight_number="LY001", scheduled_time=now + timedelta(hours=1)),
            _flight(flight_id="s2", flight_number="LY002", scheduled_time=now + timedelta(hours=2)),
        ])

        rows, _, _ = _build_query(
            db=db_session, direction="D", flight_number=None, airline_code=None,
            location=None, terminal=None,
            from_dt=now, to_dt=now + timedelta(hours=24),
            sort_by="scheduled_time", sort_order="asc", page=1, size=10,
        )

        times = [r.scheduled_time for r in rows]
        assert times == sorted(times), "Rows must be sorted ascending by scheduled_time"

    def test_sort_descending_scheduled_time(self, db_session):
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=ISRAEL_TZ)
        self._add_flights(db_session, [
            _flight(flight_id="sd1", flight_number="LY011", scheduled_time=now + timedelta(hours=1)),
            _flight(flight_id="sd2", flight_number="LY012", scheduled_time=now + timedelta(hours=2)),
        ])

        rows, _, _ = _build_query(
            db=db_session, direction="D", flight_number=None, airline_code=None,
            location=None, terminal=None,
            from_dt=now, to_dt=now + timedelta(hours=24),
            sort_by="scheduled_time", sort_order="desc", page=1, size=10,
        )

        times = [r.scheduled_time for r in rows]
        assert times == sorted(times, reverse=True)

    def test_secondary_sort_by_flight_number(self, db_session):
        """When two flights share the same scheduled_time, flight_number ASC is used."""
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=ISRAEL_TZ)
        self._add_flights(db_session, [
            _flight(flight_id="tie-b", flight_number="LY020", scheduled_time=now),
            _flight(flight_id="tie-a", flight_number="LY010", scheduled_time=now),
        ])

        rows, _, _ = _build_query(
            db=db_session, direction="D", flight_number=None, airline_code=None,
            location=None, terminal=None,
            from_dt=now - timedelta(minutes=1), to_dt=now + timedelta(hours=1),
            sort_by="scheduled_time", sort_order="asc", page=1, size=10,
        )

        flight_ids = [r.flight_id for r in rows]
        assert flight_ids.index("tie-a") < flight_ids.index("tie-b"), \
            "LY010 should appear before LY020 as secondary sort"

    # ── Cutoff / date window ────────────────────────────────────────────────

    def test_flights_before_cutoff_excluded(self, db_session):
        now = datetime(2024, 6, 15, 14, 0, 0, tzinfo=ISRAEL_TZ)
        cutoff = now - timedelta(hours=1)

        self._add_flights(db_session, [
            _flight(flight_id="old", flight_number="LY100",
                    scheduled_time=now - timedelta(hours=2)),   # too old
            _flight(flight_id="new", flight_number="LY101",
                    scheduled_time=now),                         # within window
        ])

        rows, total, _ = _build_query(
            db=db_session, direction="D", flight_number=None, airline_code=None,
            location=None, terminal=None,
            from_dt=cutoff, to_dt=now + timedelta(hours=12),
            sort_by="scheduled_time", sort_order="asc", page=1, size=10,
        )

        ids = [r.flight_id for r in rows]
        assert "old" not in ids
        assert "new" in ids

    def test_tomorrow_flights_excluded_by_default_window(self, db_session):
        now = datetime(2024, 6, 15, 14, 0, 0, tzinfo=ISRAEL_TZ)
        end_of_today = now.replace(hour=23, minute=59, second=59, microsecond=999999)

        self._add_flights(db_session, [
            _flight(flight_id="today", flight_number="LY200", scheduled_time=now + timedelta(hours=2)),
            _flight(flight_id="tomorrow", flight_number="LY201",
                    scheduled_time=now + timedelta(days=1)),
        ])

        rows, _, _ = _build_query(
            db=db_session, direction="D", flight_number=None, airline_code=None,
            location=None, terminal=None,
            from_dt=now - timedelta(hours=1), to_dt=end_of_today,
            sort_by="scheduled_time", sort_order="asc", page=1, size=10,
        )

        ids = [r.flight_id for r in rows]
        assert "today" in ids
        assert "tomorrow" not in ids

    # ── Combined filters ────────────────────────────────────────────────────

    def test_airline_and_terminal_combined(self, db_session):
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=ISRAEL_TZ)
        self._add_flights(db_session, [
            _flight(flight_id="match",   airline_code="LY", terminal="3",
                    flight_number="LY300", scheduled_time=now + timedelta(hours=1)),
            _flight(flight_id="wrong-t", airline_code="LY", terminal="1",
                    flight_number="LY301", scheduled_time=now + timedelta(hours=2)),
            _flight(flight_id="wrong-a", airline_code="AA", terminal="3",
                    flight_number="AA300", airline_name="American Airlines",
                    scheduled_time=now + timedelta(hours=3)),
        ])

        rows, total, _ = _build_query(
            db=db_session, direction="D", flight_number=None,
            airline_code="LY", location=None, terminal="3",
            from_dt=now, to_dt=now + timedelta(hours=24),
            sort_by="scheduled_time", sort_order="asc", page=1, size=10,
        )

        assert total == 1
        assert rows[0].flight_id == "match"

    def test_flight_number_partial_match(self, db_session):
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=ISRAEL_TZ)
        self._add_flights(db_session, [
            _flight(flight_id="ly400", flight_number="LY400", scheduled_time=now + timedelta(hours=1)),
            _flight(flight_id="ly401", flight_number="LY401", scheduled_time=now + timedelta(hours=2)),
            _flight(flight_id="aa400", flight_number="AA400", airline_code="AA",
                    airline_name="American Airlines", scheduled_time=now + timedelta(hours=3)),
        ])

        rows, total, _ = _build_query(
            db=db_session, direction="D", flight_number="LY4",
            airline_code=None, location=None, terminal=None,
            from_dt=now, to_dt=now + timedelta(hours=24),
            sort_by="scheduled_time", sort_order="asc", page=1, size=10,
        )

        assert total == 2
        ids = {r.flight_id for r in rows}
        assert ids == {"ly400", "ly401"}

    def test_location_matches_en_or_he(self, db_session):
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=ISRAEL_TZ)
        self._add_flights(db_session, [
            _flight(flight_id="lon-en", flight_number="LY500",
                    location_en="London", location_he="לונדון",
                    scheduled_time=now + timedelta(hours=1)),
            _flight(flight_id="par-en", flight_number="LY501",
                    location_en="Paris", location_he="פריז",
                    scheduled_time=now + timedelta(hours=2)),
        ])

        # Search by Hebrew term
        rows, total, _ = _build_query(
            db=db_session, direction="D", flight_number=None,
            airline_code=None, location="לונדון", terminal=None,
            from_dt=now, to_dt=now + timedelta(hours=24),
            sort_by="scheduled_time", sort_order="asc", page=1, size=10,
        )

        assert total == 1
        assert rows[0].flight_id == "lon-en"

    def test_direction_filter(self, db_session):
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=ISRAEL_TZ)
        self._add_flights(db_session, [
            _flight(flight_id="dep", direction="D", flight_number="LY600",
                    scheduled_time=now + timedelta(hours=1)),
            _flight(flight_id="arr", direction="A", flight_number="LY601",
                    scheduled_time=now + timedelta(hours=2)),
        ])

        rows, total, _ = _build_query(
            db=db_session, direction="D", flight_number=None,
            airline_code=None, location=None, terminal=None,
            from_dt=now, to_dt=now + timedelta(hours=24),
            sort_by="scheduled_time", sort_order="asc", page=1, size=10,
        )

        assert total == 1
        assert rows[0].flight_id == "dep"

    # ── Options endpoint ─────────────────────────────────────────────────────

    def test_options_endpoint_returns_correct_shape(self, client, db_session):
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=ISRAEL_TZ)
        db_session.add(_flight(flight_id="opt-1", scheduled_time=now))
        db_session.commit()

        r = client.get("/api/v1/flight-board/options?direction=D")
        assert r.status_code == 200
        data = r.json()
        assert set(data.keys()) == {"airlines", "cities", "terminals"}
        assert isinstance(data["airlines"], list)
        assert isinstance(data["cities"], list)
        assert isinstance(data["terminals"], list)

    def test_options_filters_by_direction(self, client, db_session):
        now = datetime(2024, 6, 15, 12, 0, 0, tzinfo=ISRAEL_TZ)
        db_session.add_all([
            _flight(flight_id="opt-d", direction="D", airline_code="LY",
                    airline_name="El Al", flight_number="LY700", scheduled_time=now),
            _flight(flight_id="opt-a", direction="A", airline_code="AA",
                    airline_name="American Airlines", flight_number="AA700", scheduled_time=now),
        ])
        db_session.commit()

        r = client.get("/api/v1/flight-board/options?direction=D")
        names = [a["name"] for a in r.json()["airlines"]]
        assert "El Al" in names
        assert "American Airlines" not in names
