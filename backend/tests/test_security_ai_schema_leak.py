"""
Security: the AI-search path must not disclose the flights table's shape.

Reported case: asking "תן לי את כל המידע" ("give me all the information") returned a
table whose headers were the real column names.

The cause was NOT `SELECT *`. Checked against the live model, the LLM faithfully selects
the 12-column subset the system prompt lists -- and those 12 are real column names, so
returning them as headers publishes the schema anyway. Deciding WHICH columns may be
read (prompt, sql_guard) is a different problem from hiding WHAT THEY ARE CALLED
(_to_public_columns). Both are covered below; the star-projection checks remain as
hardening for the case where a future model does emit SELECT *.

These tests deliberately exercise pure functions (sql_guard.validate_and_prepare and
ai_search._to_public_columns) so they need no database. The earlier AI tests required
Postgres for the rate-limit counter tables and SKIPPED, which is why this was missed.

Run:  pytest tests/test_security_ai_schema_leak.py -v
"""
import pytest

from app.services.ai_search import _to_public_columns
from app.services.sql_guard import SqlGuardError, validate_and_prepare

# Present on the model, must never be selectable by the AI path.
INTERNAL_COLUMNS = [
    "raw_s3_path",
    "scrape_timestamp",
    "checkin_counters",
    "checkin_zone",
]


class TestStarProjectionRejected:
    """The exact reported failure."""

    @pytest.mark.parametrize("sql", [
        "SELECT * FROM flights",
        "SELECT * FROM flights LIMIT 50",
        "select * from flights where direction = 'D'",
        "SELECT flights.* FROM flights",
        "SELECT f.* FROM flights f",
        "SELECT * FROM (SELECT * FROM flights) t",
    ])
    def test_star_projection_is_rejected(self, sql):
        with pytest.raises(SqlGuardError):
            validate_and_prepare(sql, max_rows=50)

    def test_count_star_is_still_allowed(self):
        """
        COUNT(*) must keep working -- the system prompt requires it for the
        count-distinct answers. A blanket ban on Star nodes would break them.
        """
        out = validate_and_prepare(
            "SELECT airline_name, COUNT(*) AS total_flights FROM flights "
            "GROUP BY airline_name",
            max_rows=50,
        )
        assert "COUNT(*)" in out.upper()


class TestInternalColumnsRejected:

    @pytest.mark.parametrize("column", INTERNAL_COLUMNS)
    def test_cannot_select_internal_column(self, column):
        with pytest.raises(SqlGuardError):
            validate_and_prepare(f"SELECT {column} FROM flights LIMIT 10", max_rows=50)

    @pytest.mark.parametrize("column", INTERNAL_COLUMNS)
    def test_cannot_filter_on_internal_column(self, column):
        """Filtering leaks by inference even when the column is not projected."""
        with pytest.raises(SqlGuardError):
            validate_and_prepare(
                f"SELECT airline_name FROM flights WHERE {column} IS NOT NULL LIMIT 10",
                max_rows=50,
            )

    def test_cannot_alias_an_internal_column(self):
        """Renaming the output must not smuggle the value out."""
        with pytest.raises(SqlGuardError):
            validate_and_prepare(
                "SELECT raw_s3_path AS airline_name FROM flights LIMIT 10", max_rows=50
            )

    def test_cannot_reach_internal_column_through_a_cte(self):
        with pytest.raises(SqlGuardError):
            validate_and_prepare(
                "WITH t AS (SELECT raw_s3_path AS x FROM flights) SELECT x FROM t",
                max_rows=50,
            )


class TestLegitimateQueriesStillWork:
    """The guard must not break the queries the feature exists to serve."""

    @pytest.mark.parametrize("sql", [
        "SELECT airline_name, COUNT(*) AS total_flights FROM flights "
        "WHERE direction = 'D' GROUP BY airline_name HAVING COUNT(*) >= 10",

        "SELECT location_city_en AS destination, ROUND(AVG(delay_minutes), 1) AS avg_delay_minutes "
        "FROM flights WHERE direction = 'D' GROUP BY location_city_en",

        "SELECT COUNT(DISTINCT airline_name) AS total_flights FROM flights WHERE direction = 'D'",

        "SELECT airline_name, status_en, delay_minutes, scheduled_time FROM flights "
        "WHERE country_en ILIKE '%greece%' ORDER BY scheduled_time DESC",

        "SELECT airline_name, COUNT(*) AS total_flights FROM flights "
        "GROUP BY airline_name ORDER BY total_flights DESC",
    ])
    def test_valid_query_passes(self, sql):
        out = validate_and_prepare(sql, max_rows=50)
        assert "LIMIT" in out.upper()


class TestColumnNamesAreNeverPublished:
    """
    The reported failure, precisely.

    The model does NOT emit `SELECT *` -- it faithfully selects the 12 columns the
    system prompt lists. But those 12 are real column names, so returning them as table
    headers publishes the schema just as surely as SELECT * would. Restricting WHICH
    columns may be read is not the same as hiding WHAT THEY ARE CALLED.
    """

    # Exactly what the LLM generates for "תן לי את כל המידע" (verified against Gemini).
    LLM_SELECTED = [
        "airline_name", "airline_code", "direction", "location_en", "location_he",
        "location_city_en", "country_en", "scheduled_time", "actual_time",
        "delay_minutes", "status_en", "terminal",
    ]

    def test_give_me_everything_returns_no_column_names(self):
        rows = [{c: "x" for c in self.LLM_SELECTED}]

        columns, public_rows = _to_public_columns(self.LLM_SELECTED, rows)

        for raw in self.LLM_SELECTED:
            assert raw not in columns, f"raw column {raw!r} published as a header"
            assert raw not in public_rows[0], f"raw column {raw!r} published as a row key"

    def test_answer_still_carries_the_same_data(self):
        """Hiding the schema must not empty the answer."""
        rows = [{c: f"v_{c}" for c in self.LLM_SELECTED}]

        columns, public_rows = _to_public_columns(self.LLM_SELECTED, rows)

        assert len(columns) == len(self.LLM_SELECTED)
        assert sorted(public_rows[0].values()) == sorted(rows[0].values())

    def test_no_label_round_trips_to_a_column_name(self):
        """
        A label like "Terminal" lowercases straight back to the column `terminal`,
        which hands over the identifier anyway. Every label must break that mapping.
        """
        from app.services.ai_search import _PUBLIC_LABELS, _REAL_COLUMNS

        offenders = [
            (col, label)
            for col, label in _PUBLIC_LABELS.items()
            if label.lower().replace(" ", "_") in _REAL_COLUMNS
        ]
        assert not offenders, f"labels that reveal their column: {offenders}"

    @pytest.mark.parametrize("column", INTERNAL_COLUMNS)
    def test_internal_columns_have_no_label_at_all(self, column):
        from app.services.ai_search import _public_label

        assert _public_label(column) is None

    def test_unknown_real_column_is_dropped_not_guessed(self):
        """
        A column added to the table later must not become visible by default --
        fail closed, the same rule the REST allowlist follows.
        """
        columns, rows = _to_public_columns(
            ["airline_name", "some_new_internal_col"],
            [{"airline_name": "El Al", "some_new_internal_col": "secret"}],
        )
        assert "some_new_internal_col" not in columns
        assert "secret" not in str(rows) or "Some New Internal Col" in columns

    def test_handler_aliases_are_relabelled_too(self):
        """The handler path emits airline_name as well -- it is not fallback-only."""
        columns, _ = _to_public_columns(
            ["airline_name", "total_flights", "on_time_pct"],
            [{"airline_name": "El Al", "total_flights": 10, "on_time_pct": 88.0}],
        )
        assert "airline_name" not in columns
        assert columns == ["Airline", "Total Flights", "On-Time %"]


class TestPostExecutionBackstop:
    """
    Independent of the parser: whatever SQL ran, internal columns are dropped on the
    way out. Guards against a projection form sqlglot models differently than expected.
    """

    def test_internal_columns_are_stripped_from_results(self):
        columns = ["airline_name", "raw_s3_path", "delay_minutes", "scrape_timestamp"]
        rows = [
            {
                "airline_name": "El Al",
                "raw_s3_path": "s3://rankair-raw/flights/2026/07/25/1.json",
                "delay_minutes": 12,
                "scrape_timestamp": "2026-07-25T08:00:00",
            }
        ]

        out_cols, out_rows = _to_public_columns(columns, rows)

        assert out_cols == ["Airline", "Delay (minutes)"]
        assert out_rows == [{"Airline": "El Al", "Delay (minutes)": 12}]
        assert "s3://" not in str(out_rows)

    def test_values_survive_relabelling(self):
        columns = ["airline_name", "total_flights"]
        rows = [{"airline_name": "El Al", "total_flights": 42}]

        out_cols, out_rows = _to_public_columns(columns, rows)

        assert out_cols == ["Airline", "Total Flights"]
        assert out_rows == [{"Airline": "El Al", "Total Flights": 42}]

    def test_stripping_is_case_insensitive(self):
        out_cols, out_rows = _to_public_columns(
            ["Airline_Name", "RAW_S3_PATH"],
            [{"Airline_Name": "El Al", "RAW_S3_PATH": "s3://bucket/k.json"}],
        )
        assert out_cols == ["Airline"]
        assert out_rows == [{"Airline": "El Al"}]
