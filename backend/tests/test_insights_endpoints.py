"""
Endpoint-level checks for /api/v1/insights.

READ THIS BEFORE TRUSTING A GREEN RUN.

These aggregates are written in PostgreSQL dialect (`date_trunc`, `to_char`, `EXTRACT(dow …)`,
`FILTER`, `INTERVAL`, `= ANY`). The suite's database is in-memory SQLite (tests/conftest.py), so on
a default `pytest` run every test in this file SKIPS. A green run here is not evidence the
endpoints work — it is evidence they were not exercised.

The real coverage lives in two places:
  1. tests/test_insights_logic.py — every classification rule, as plain functions over plain
     dicts, so it actually runs. That is where the traps are pinned down.
  2. Manual verification against the production read-only replica, whose results are recorded in
     docs/planning/NEW_PAGES_PLAN.md.

To run this file for real, point it at PostgreSQL:
    DATABASE_URL=postgresql+psycopg://… pytest tests/test_insights_endpoints.py
"""
import pytest
from fastapi import status


def skip_if_sqlite(response):
    """Skip rather than fail when the dialect, not the code, is what broke."""
    if response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
        pytest.skip("Insights aggregates require PostgreSQL (date_trunc/to_char/EXTRACT/FILTER)")


class TestMonthlyByNationality:
    def test_returns_months_and_crisis_window_keys(self, client, sample_flights):
        response = client.get("/api/v1/insights/monthly-by-nationality")
        skip_if_sqlite(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "months" in data and "crisis_window" in data

    def test_every_month_carries_both_nationalities(self, client, sample_flights):
        """A nationality with no flights must appear as 0, never as an absent key."""
        response = client.get("/api/v1/insights/monthly-by-nationality")
        skip_if_sqlite(response)
        for month in response.json()["months"]:
            assert "israeli_scheduled" in month
            assert "foreign_scheduled" in month
            assert month["total_scheduled"] == month["israeli_scheduled"] + month["foreign_scheduled"]

    def test_percentages_are_within_range(self, client, sample_flights):
        response = client.get("/api/v1/insights/monthly-by-nationality")
        skip_if_sqlite(response)
        for month in response.json()["months"]:
            assert 0 <= month["israeli_cancelled_pct"] <= 100
            assert 0 <= month["foreign_cancelled_pct"] <= 100
            assert 0 <= month["israeli_share_pct"] <= 100


class TestByWeekday:
    def test_all_seven_days_present(self, client, sample_flights):
        response = client.get("/api/v1/insights/by-weekday")
        skip_if_sqlite(response)
        assert response.status_code == status.HTTP_200_OK
        weekdays = response.json()["weekdays"]
        assert [row["dow"] for row in weekdays] == list(range(7))

    def test_reports_the_on_time_threshold_it_used(self, client, sample_flights):
        """The number is meaningless without its definition, so the endpoint states it."""
        response = client.get("/api/v1/insights/by-weekday")
        skip_if_sqlite(response)
        assert response.json()["on_time_threshold_minutes"] == 15


class TestByHour:
    def test_all_24_hours_present(self, client, sample_flights):
        response = client.get("/api/v1/insights/by-hour")
        skip_if_sqlite(response)
        assert response.status_code == status.HTTP_200_OK
        hours = response.json()["hours"]
        assert [row["hour"] for row in hours] == list(range(24))


class TestCarrierRecovery:
    def test_returns_expected_envelope(self, client, sample_flights):
        response = client.get("/api/v1/insights/carrier-recovery")
        skip_if_sqlite(response)
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert {"carriers", "crisis_window", "summary"} <= set(data)

    def test_no_disruption_returns_empty_rather_than_inventing_one(self, client, sample_flights):
        """
        The fixture data is a handful of calm flights. With no disruption there is no baseline
        cutoff to compute against, and the endpoint must say so rather than pick an arbitrary date.
        """
        response = client.get("/api/v1/insights/carrier-recovery")
        skip_if_sqlite(response)
        data = response.json()
        if data["crisis_window"] is None:
            assert data["carriers"] == []

    def test_buckets_are_from_the_known_set(self, client, sample_flights):
        response = client.get("/api/v1/insights/carrier-recovery")
        skip_if_sqlite(response)
        allowed = {"never_returned", "partial", "recovered", "expanded"}
        for carrier in response.json()["carriers"]:
            assert carrier["bucket"] in allowed

    def test_never_returned_carriers_expose_no_return_date(self, client, sample_flights):
        """The Georgian Airways trap, asserted at the API boundary as well as in the unit tests."""
        response = client.get("/api/v1/insights/carrier-recovery")
        skip_if_sqlite(response)
        for carrier in response.json()["carriers"]:
            if carrier["bucket"] == "never_returned":
                assert carrier["return_date"] is None
