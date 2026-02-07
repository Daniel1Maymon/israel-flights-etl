import hashlib
import os
from unittest.mock import patch, MagicMock
import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Config tests
# ---------------------------------------------------------------------------

class TestConfig:
    def test_defaults(self):
        """Config should provide sensible defaults when env vars are unset."""
        env = {
            "POSTGRES_FLIGHTS_HOST": "",
            "POSTGRES_FLIGHTS_PORT": "",
            "POSTGRES_FLIGHTS_DB": "",
            "POSTGRES_FLIGHTS_USER": "",
            "POSTGRES_FLIGHTS_PASSWORD": "",
            "CKAN_BASE_URL": "",
            "CKAN_RESOURCE_ID": "",
            "CKAN_BATCH_SIZE": "",
            "SCHEDULE_INTERVAL_MINUTES": "",
        }
        with patch.dict(os.environ, env, clear=False):
            # Re-import to pick up patched env
            import importlib
            import etl.config as cfg_mod
            importlib.reload(cfg_mod)
            cfg = cfg_mod.get_config()

        assert cfg["ckan_base_url"] == "https://data.gov.il/api/3/action/datastore_search"
        assert cfg["ckan_resource_id"] == "e83f763b-b7d7-479e-b172-ae981ddc6de5"
        assert cfg["ckan_batch_size"] == 1000
        assert cfg["schedule_interval_minutes"] == 15
        assert cfg["pg_host"] == "postgres_flights"
        assert cfg["pg_port"] == 5432
        assert cfg["pg_database"] == "flights_db"
        assert cfg["pg_user"] == "daniel"
        assert cfg["pg_password"] == "daniel"

    def test_env_overrides(self):
        """Config values should come from environment variables when set."""
        env = {
            "POSTGRES_FLIGHTS_HOST": "myhost",
            "POSTGRES_FLIGHTS_PORT": "9999",
            "POSTGRES_FLIGHTS_DB": "mydb",
            "POSTGRES_FLIGHTS_USER": "myuser",
            "POSTGRES_FLIGHTS_PASSWORD": "secret",
            "CKAN_BASE_URL": "https://custom.api/search",
            "CKAN_RESOURCE_ID": "abc-123",
            "CKAN_BATCH_SIZE": "500",
            "SCHEDULE_INTERVAL_MINUTES": "30",
        }
        with patch.dict(os.environ, env, clear=False):
            import importlib
            import etl.config as cfg_mod
            importlib.reload(cfg_mod)
            cfg = cfg_mod.get_config()

        assert cfg["pg_host"] == "myhost"
        assert cfg["pg_port"] == 9999
        assert cfg["pg_database"] == "mydb"
        assert cfg["pg_user"] == "myuser"
        assert cfg["pg_password"] == "secret"
        assert cfg["ckan_base_url"] == "https://custom.api/search"
        assert cfg["ckan_resource_id"] == "abc-123"
        assert cfg["ckan_batch_size"] == 500
        assert cfg["schedule_interval_minutes"] == 30


# ---------------------------------------------------------------------------
# Fetch tests
# ---------------------------------------------------------------------------

class TestFetch:
    def _make_response(self, records, status_code=200):
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = {"result": {"records": records}}
        return resp

    @patch("etl.fetch.requests.get")
    def test_single_page(self, mock_get):
        """Fetch should return all records from a single page."""
        from etl.fetch import fetch_flights

        records = [{"CHOPER": "LY", "CHFLTN": "001"}]
        mock_get.return_value = self._make_response(records)

        # Second call returns empty to stop pagination
        mock_get.side_effect = [
            self._make_response(records),
            self._make_response([]),
        ]

        result = fetch_flights(
            base_url="https://example.com/api",
            resource_id="res-1",
            batch_size=1000,
        )
        assert result == records

    @patch("etl.fetch.requests.get")
    def test_pagination(self, mock_get):
        """Fetch should paginate through multiple pages of results."""
        from etl.fetch import fetch_flights

        page1 = [{"id": 1}, {"id": 2}]
        page2 = [{"id": 3}]

        mock_get.side_effect = [
            self._make_response(page1),
            self._make_response(page2),
            self._make_response([]),
        ]

        result = fetch_flights(
            base_url="https://example.com/api",
            resource_id="res-1",
            batch_size=2,
        )
        assert result == page1 + page2

    @patch("etl.fetch.requests.get")
    def test_empty_response(self, mock_get):
        """Fetch should return empty list when API has no records."""
        from etl.fetch import fetch_flights

        mock_get.return_value = self._make_response([])

        result = fetch_flights(
            base_url="https://example.com/api",
            resource_id="res-1",
            batch_size=1000,
        )
        assert result == []

    @patch("etl.fetch.requests.get")
    def test_api_error(self, mock_get):
        """Fetch should raise on non-200 status code."""
        from etl.fetch import fetch_flights

        mock_get.return_value = self._make_response([], status_code=500)

        with pytest.raises(Exception, match="API request failed"):
            fetch_flights(
                base_url="https://example.com/api",
                resource_id="res-1",
                batch_size=1000,
            )

    @patch("etl.fetch.requests.get")
    def test_request_exception(self, mock_get):
        """Fetch should propagate network errors."""
        from etl.fetch import fetch_flights
        import requests

        mock_get.side_effect = requests.ConnectionError("no network")

        with pytest.raises(requests.ConnectionError):
            fetch_flights(
                base_url="https://example.com/api",
                resource_id="res-1",
                batch_size=1000,
            )


# ---------------------------------------------------------------------------
# Transform tests
# ---------------------------------------------------------------------------

class TestTransform:
    SAMPLE_RECORDS = [
        {
            "CHOPER": "LY",
            "CHFLTN": "001",
            "CHOPERD": "El Al",
            "CHSTOL": "2025-01-15T10:00:00",
            "CHPTOL": "2025-01-15T10:30:00",
            "CHAORD": "D",
            "CHLOC1": "JFK",
            "CHLOC1D": "New York JFK",
            "CHLOC1TH": "ניו יורק",
            "CHLOC1T": "New York",
            "CHLOC1CH": "ארצות הברית",
            "CHLOCCT": "United States",
            "CHTERM": "3",
            "CHCINT": "12:00",
            "CHCKZN": "A",
            "CHRMINE": "DEPARTED",
            "CHRMINH": "יצא",
        }
    ]

    def test_column_renaming(self):
        """All 17 Hebrew columns should be renamed to English."""
        from etl.transform import transform_records

        df = transform_records(self.SAMPLE_RECORDS)

        expected_cols = [
            "airline_code", "flight_number", "airline_name",
            "scheduled_departure_time", "actual_departure_time",
            "arrival_departure_code", "airport_code",
            "airport_name_english", "airport_name_hebrew",
            "city_name_english", "country_name_hebrew",
            "country_name_english", "terminal_number",
            "check_in_time", "check_in_zone",
            "status_english", "status_hebrew",
        ]
        for col in expected_cols:
            assert col in df.columns, f"Missing column: {col}"

    def test_delay_calculation(self):
        """delay_minutes should be (actual - scheduled) in minutes."""
        from etl.transform import transform_records

        df = transform_records(self.SAMPLE_RECORDS)

        assert "delay_minutes" in df.columns
        assert df.iloc[0]["delay_minutes"] == 30.0

    def test_negative_delay(self):
        """Early arrival should produce a negative delay."""
        from etl.transform import transform_records

        records = [dict(self.SAMPLE_RECORDS[0])]
        records[0]["CHPTOL"] = "2025-01-15T09:45:00"  # 15 min early

        df = transform_records(records)
        assert df.iloc[0]["delay_minutes"] == -15.0

    def test_nat_handling(self):
        """Missing actual time should produce NaN delay, not crash."""
        from etl.transform import transform_records

        records = [dict(self.SAMPLE_RECORDS[0])]
        records[0]["CHPTOL"] = None

        df = transform_records(records)
        assert pd.isna(df.iloc[0]["delay_minutes"])

    def test_empty_input(self):
        """Empty input should return empty DataFrame."""
        from etl.transform import transform_records

        df = transform_records([])
        assert df.empty

    def test_scheduled_actual_datetime_columns(self):
        """Transform should create scheduled_departure and actual_departure columns."""
        from etl.transform import transform_records

        df = transform_records(self.SAMPLE_RECORDS)
        assert "scheduled_departure" in df.columns
        assert "actual_departure" in df.columns
        assert pd.notna(df.iloc[0]["scheduled_departure"])


# ---------------------------------------------------------------------------
# Load tests
# ---------------------------------------------------------------------------

class TestLoad:
    def test_compute_flight_uuid(self):
        """UUID should be MD5 of the natural key."""
        from etl.load import compute_flight_uuid

        row = pd.Series({
            "airline_code": "LY",
            "flight_number": "001",
            "arrival_departure_code": "D",
            "airport_code": "JFK",
            "scheduled_departure": "2025-01-15 10:00:00",
        })

        result = compute_flight_uuid(row)
        expected_key = "LY_001_D_JFK_2025-01-15 10:00:00"
        expected = hashlib.md5(expected_key.encode()).hexdigest()
        assert result == expected

    def test_uuid_deterministic(self):
        """Same inputs should always produce the same UUID."""
        from etl.load import compute_flight_uuid

        row = pd.Series({
            "airline_code": "LY",
            "flight_number": "001",
            "arrival_departure_code": "D",
            "airport_code": "JFK",
            "scheduled_departure": "2025-01-15 10:00:00",
        })

        assert compute_flight_uuid(row) == compute_flight_uuid(row)

    def test_uuid_differs_for_different_flights(self):
        """Different flights should produce different UUIDs."""
        from etl.load import compute_flight_uuid

        row1 = pd.Series({
            "airline_code": "LY",
            "flight_number": "001",
            "arrival_departure_code": "D",
            "airport_code": "JFK",
            "scheduled_departure": "2025-01-15 10:00:00",
        })
        row2 = pd.Series({
            "airline_code": "LY",
            "flight_number": "002",
            "arrival_departure_code": "D",
            "airport_code": "JFK",
            "scheduled_departure": "2025-01-15 10:00:00",
        })

        assert compute_flight_uuid(row1) != compute_flight_uuid(row2)

    def test_create_table_ddl(self):
        """create_flights_table should execute CREATE TABLE IF NOT EXISTS."""
        from etl.load import create_flights_table_if_not_exists

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        create_flights_table_if_not_exists(mock_conn)

        mock_cursor.execute.assert_called_once()
        sql = mock_cursor.execute.call_args[0][0]
        assert "CREATE TABLE IF NOT EXISTS flights" in sql
        assert "flight_id" in sql
        assert "airline_code" in sql
        mock_conn.commit.assert_called_once()

    def test_upsert_sql(self):
        """upsert_flight_data should use INSERT ... ON CONFLICT DO UPDATE."""
        from etl.load import upsert_flight_data

        df = pd.DataFrame([{
            "flight_id": "abc123",
            "airline_code": "LY",
            "flight_number": "001",
            "arrival_departure_code": "D",
            "airport_code": "JFK",
            "scheduled_departure": pd.Timestamp("2025-01-15 10:00:00"),
            "actual_departure": pd.Timestamp("2025-01-15 10:30:00"),
            "airline_name": "El Al",
            "airport_name_english": "JFK",
            "airport_name_hebrew": "ג'יי אף קיי",
            "city_name_english": "New York",
            "country_name_english": "US",
            "country_name_hebrew": "ארה\"ב",
            "terminal_number": "3",
            "check_in_time": "12:00",
            "check_in_zone": "A",
            "status_english": "DEPARTED",
            "status_hebrew": "יצא",
            "delay_minutes": 30,
            "scheduled_departure_time": "2025-01-15T10:00:00",
            "actual_departure_time": "2025-01-15T10:30:00",
        }])

        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor

        rows = upsert_flight_data(df, mock_conn)

        assert rows == 1
        sql = mock_cursor.executemany.call_args[0][0]
        assert "INSERT INTO flights" in sql
        assert "ON CONFLICT (flight_id) DO UPDATE SET" in sql
        mock_conn.commit.assert_called_once()

    def test_upsert_empty_df(self):
        """upsert_flight_data should return 0 for empty DataFrame."""
        from etl.load import upsert_flight_data

        df = pd.DataFrame()
        mock_conn = MagicMock()

        rows = upsert_flight_data(df, mock_conn)
        assert rows == 0


# ---------------------------------------------------------------------------
# Pipeline tests
# ---------------------------------------------------------------------------

class TestPipeline:
    @patch("etl.main.load_to_db")
    @patch("etl.main.transform_records")
    @patch("etl.main.fetch_flights")
    @patch("etl.main.get_config")
    def test_run_pipeline_orchestration(self, mock_cfg, mock_fetch, mock_transform, mock_load):
        """run_pipeline should call fetch -> transform -> load in order."""
        from etl.main import run_pipeline

        mock_cfg.return_value = {
            "ckan_base_url": "https://example.com/api",
            "ckan_resource_id": "res-1",
            "ckan_batch_size": 1000,
            "pg_host": "localhost",
            "pg_port": 5432,
            "pg_database": "testdb",
            "pg_user": "user",
            "pg_password": "pass",
        }
        mock_fetch.return_value = [{"CHOPER": "LY"}]
        mock_transform.return_value = pd.DataFrame({"flight_id": ["abc"]})

        run_pipeline()

        mock_fetch.assert_called_once()
        mock_transform.assert_called_once_with([{"CHOPER": "LY"}])
        mock_load.assert_called_once()

    @patch("etl.main.load_to_db")
    @patch("etl.main.transform_records")
    @patch("etl.main.fetch_flights")
    @patch("etl.main.get_config")
    def test_run_pipeline_empty_fetch(self, mock_cfg, mock_fetch, mock_transform, mock_load):
        """Pipeline should skip transform/load when fetch returns nothing."""
        from etl.main import run_pipeline

        mock_cfg.return_value = {
            "ckan_base_url": "https://example.com/api",
            "ckan_resource_id": "res-1",
            "ckan_batch_size": 1000,
            "pg_host": "localhost",
            "pg_port": 5432,
            "pg_database": "testdb",
            "pg_user": "user",
            "pg_password": "pass",
        }
        mock_fetch.return_value = []

        run_pipeline()

        mock_fetch.assert_called_once()
        mock_transform.assert_not_called()
        mock_load.assert_not_called()

    @patch("etl.main.fetch_flights")
    @patch("etl.main.get_config")
    def test_run_pipeline_fetch_error(self, mock_cfg, mock_fetch):
        """Pipeline should propagate fetch errors."""
        from etl.main import run_pipeline

        mock_cfg.return_value = {
            "ckan_base_url": "https://example.com/api",
            "ckan_resource_id": "res-1",
            "ckan_batch_size": 1000,
            "pg_host": "localhost",
            "pg_port": 5432,
            "pg_database": "testdb",
            "pg_user": "user",
            "pg_password": "pass",
        }
        mock_fetch.side_effect = Exception("API down")

        with pytest.raises(Exception, match="API down"):
            run_pipeline()
