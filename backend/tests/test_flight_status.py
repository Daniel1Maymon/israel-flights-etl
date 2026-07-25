"""
Tests for the canonical cancellation definition.

These run against the SQLite test database via the ORM predicate, so unlike the endpoint tests they
actually execute. The raw-SQL fragment cannot be exercised here (SQLite has no ILIKE), so the
string form is asserted structurally instead — the two must stay equivalent, which is the entire
reason flight_status.py exists.
"""
from datetime import datetime, timedelta

import pytest

from app.models.flight import Flight
from app.services.flight_status import (
    CANCELLED_SQL,
    MAX_PLAUSIBLE_DELAY_MIN,
    NOT_CANCELLED_SQL,
    is_cancelled,
)


def make_flight(db, flight_id, *, status_en="DEPARTED", status_he="המריאה", delay=10):
    now = datetime(2026, 4, 1, 12, 0, 0)
    flight = Flight(
        flight_id=flight_id,
        airline_code="LY",
        flight_number=flight_id,
        direction="D",
        location_iata="LCA",
        location_en="Larnaca",
        location_he="לרנקה",
        location_city_en="LARNACA",
        country_en="Cyprus",
        country_he="קפריסין",
        airline_name="EL AL ISRAEL AIRLINES",
        scheduled_time=now,
        actual_time=now + timedelta(minutes=delay) if delay is not None else None,
        delay_minutes=delay,
        terminal="3",
        status_en=status_en,
        status_he=status_he,
        scrape_timestamp=now,
    )
    db.add(flight)
    db.commit()
    return flight


def cancelled_ids(db):
    return {f.flight_id for f in db.query(Flight).filter(is_cancelled(Flight)).all()}


class TestStatusBasedCancellation:
    def test_english_status_matches_either_spelling(self, db_session):
        make_flight(db_session, "us", status_en="CANCELED")
        make_flight(db_session, "uk", status_en="CANCELLED")
        make_flight(db_session, "lower", status_en="cancelled")
        assert cancelled_ids(db_session) == {"us", "uk", "lower"}

    def test_hebrew_status_is_a_redundant_safety_net(self, db_session):
        make_flight(db_session, "he", status_en="UNKNOWN", status_he="מבוטלת")
        assert cancelled_ids(db_session) == {"he"}

    def test_ordinary_flight_is_not_cancelled(self, db_session):
        make_flight(db_session, "fine", delay=25)
        assert cancelled_ids(db_session) == set()


class TestImplausibleDelayIsACancellation:
    """
    A flight that departs more than a day late was cancelled and rebooked; the upstream feed just
    never changed the status. Production had eight such rows recorded as DEPARTED or LANDED, and
    they poisoned every delay statistic they touched — Arkia's worst delay read 2,883 minutes, ten
    times its own 99th percentile.
    """

    def test_two_day_delay_counts_as_cancelled(self, db_session):
        make_flight(db_session, "arkia-larnaca", status_en="DEPARTED", delay=2883)
        assert cancelled_ids(db_session) == {"arkia-larnaca"}

    def test_delay_just_over_the_line_counts_as_cancelled(self, db_session):
        make_flight(db_session, "over", delay=MAX_PLAUSIBLE_DELAY_MIN + 1)
        assert cancelled_ids(db_session) == {"over"}

    def test_delay_exactly_at_the_line_is_still_a_delay(self, db_session):
        make_flight(db_session, "boundary", delay=MAX_PLAUSIBLE_DELAY_MIN)
        assert cancelled_ids(db_session) == set()

    def test_long_but_plausible_delay_stays_a_delay(self, db_session):
        """A 12-hour delay is miserable but real, and must not be reclassified away."""
        make_flight(db_session, "twelve-hours", delay=720)
        assert cancelled_ids(db_session) == set()

    def test_null_delay_is_not_swallowed(self, db_session):
        """
        The COALESCE guard. Without it the comparison is NULL for a missing delay, `status OR NULL`
        is NULL, and NOT NULL is NULL too — so the row would vanish from BOTH the cancelled and the
        not-cancelled sets, silently dropping out of every aggregate on the site.
        """
        make_flight(db_session, "no-actual-time", delay=None)
        assert cancelled_ids(db_session) == set()
        not_cancelled = db_session.query(Flight).filter(~is_cancelled(Flight)).all()
        assert {f.flight_id for f in not_cancelled} == {"no-actual-time"}

    def test_cancelled_status_wins_regardless_of_delay(self, db_session):
        make_flight(db_session, "both", status_en="CANCELED", delay=5)
        assert cancelled_ids(db_session) == {"both"}


class TestSqlAndOrmStayEquivalent:
    """The two forms are used in different call sites; drift between them is the failure mode."""

    def test_sql_fragment_covers_all_three_conditions(self):
        assert "status_en ILIKE '%cancel%'" in CANCELLED_SQL
        assert "status_he ILIKE '%בוטל%'" in CANCELLED_SQL
        assert f"COALESCE(delay_minutes, 0) > {MAX_PLAUSIBLE_DELAY_MIN}" in CANCELLED_SQL

    def test_not_cancelled_is_the_negation(self):
        assert NOT_CANCELLED_SQL == f"NOT {CANCELLED_SQL}"

    def test_threshold_is_at_least_a_full_day(self):
        """Guards against someone tightening it to a value that would erase genuine delays."""
        assert MAX_PLAUSIBLE_DELAY_MIN >= 1440
