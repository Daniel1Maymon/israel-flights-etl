"""
Pytest configuration and fixtures for backend API tests

Best Practices:
1. Tests are isolated - each test gets a fresh database session with transaction rollback
2. No global state mutations - production models are never modified
3. Proper cleanup - transactions rollback, tables are cleaned up
4. Type compatibility - handles PostgreSQL TIMESTAMP -> SQLite DateTime conversion
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from sqlalchemy.types import TypeDecorator, DateTime as SQLDateTime
from datetime import datetime, timedelta
from typing import Generator
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from app.database import Base, get_db
from app.models.flight import Flight


# Type adapter to convert PostgreSQL TIMESTAMP to SQLite-compatible DateTime
class SQLiteDateTime(TypeDecorator):
    """Converts PostgreSQL TIMESTAMP(timezone=True) to SQLite-compatible DateTime"""
    impl = SQLDateTime
    cache_ok = True


# Test database URL (using in-memory SQLite for testing)
TEST_DATABASE_URL = "sqlite:///:memory:"

# Create test engine with type conversion
test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

# Map PostgreSQL TIMESTAMP to SQLite DateTime for table creation
@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """Set SQLite pragmas for better compatibility"""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


# Create test session factory
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """
    Create a fresh database session for each test.
    
    Uses transaction rollback for proper isolation:
    - Each test runs in its own transaction
    - Transaction is rolled back after test completes
    - Tables are created fresh for each test
    - No test can affect another test's data
    
    This is the proper way to ensure test isolation.
    """
    # For SQLite compatibility, we need to replace PostgreSQL TIMESTAMP types
    # Access the Column objects through the table metadata
    from sqlalchemy import DateTime
    
    # Get the table and columns
    flight_table = Flight.__table__
    
    # Store original column types
    original_types = {}
    for col_name in ['scheduled_time', 'actual_time', 'scrape_timestamp']:
        col = flight_table.columns[col_name]
        original_types[col_name] = col.type
    
    try:
        # Replace PostgreSQL TIMESTAMP with DateTime for SQLite compatibility
        for col_name in ['scheduled_time', 'actual_time', 'scrape_timestamp']:
            col = flight_table.columns[col_name]
            col.type = DateTime()
        
        # Create tables
        Base.metadata.create_all(bind=test_engine)
        
        # Create a connection and start a transaction
        connection = test_engine.connect()
        transaction = connection.begin()
        
        # Bind session to the connection
        session = TestingSessionLocal(bind=connection)
        
        try:
            yield session
        finally:
            # Rollback transaction (this ensures test isolation)
            session.close()
            transaction.rollback()
            connection.close()
            
            # Drop tables
            Base.metadata.drop_all(bind=test_engine)
    finally:
        # Restore original types (critical - don't mutate production model!)
        for col_name, original_type in original_types.items():
            col = flight_table.columns[col_name]
            col.type = original_type


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """
    Create a test client with database dependency overrides.
    
    This fixture:
    - Overrides get_db and get_database dependencies to use test session
    - Ensures proper cleanup after each test
    - Provides a TestClient for making HTTP requests
    """
    def override_get_db() -> Generator[Session, None, None]:
        """Override get_db dependency to use test session"""
        try:
            yield db_session
        finally:
            # Session is managed by db_session fixture
            pass
    
    def override_get_database() -> Generator[Session, None, None]:
        """Override get_database dependency to use test session"""
        try:
            yield db_session
        except Exception as e:
            db_session.rollback()
            raise
        finally:
            pass
    
    # Override dependencies
    app.dependency_overrides[get_db] = override_get_db
    
    try:
        from app.api.deps import get_database
        app.dependency_overrides[get_database] = override_get_database
    except ImportError:
        pass
    
    # Create test client
    with TestClient(app) as test_client:
        yield test_client
    
    # Clean up - remove all dependency overrides
    app.dependency_overrides.clear()


@pytest.fixture
def sample_flights(db_session: Session) -> list:
    """
    Create sample flight data for testing.
    
    This fixture creates test data that is automatically cleaned up
    via transaction rollback after each test completes.
    """
    now = datetime.utcnow()
    
    flights = [
        Flight(
            flight_id="test-flight-1",
            airline_code="LY",
            flight_number="LY001",
            direction="D",
            location_iata="JFK",
            location_en="New York",
            location_he="ניו יורק",
            location_city_en="New York",
            country_en="United States",
            country_he="ארצות הברית",
            airline_name="El Al",
            scheduled_time=now + timedelta(hours=2),
            actual_time=None,
            delay_minutes=0,
            terminal="3",
            checkin_counters="1-10",
            checkin_zone="A",
            status_en="On Time",
            status_he="בזמן",
            scrape_timestamp=now,
            raw_s3_path="s3://bucket/path/to/file.json"
        ),
        Flight(
            flight_id="test-flight-2",
            airline_code="DL",
            flight_number="DL123",
            direction="A",
            location_iata="TLV",
            location_en="Tel Aviv",
            location_he="תל אביב",
            location_city_en="Tel Aviv",
            country_en="Israel",
            country_he="ישראל",
            airline_name="Delta Air Lines",
            scheduled_time=now + timedelta(hours=1),
            actual_time=now + timedelta(hours=1, minutes=15),
            delay_minutes=15,
            terminal="3",
            checkin_counters=None,
            checkin_zone=None,
            status_en="Delayed",
            status_he="איחור",
            scrape_timestamp=now,
            raw_s3_path="s3://bucket/path/to/file2.json"
        ),
        Flight(
            flight_id="test-flight-3",
            airline_code="UA",
            flight_number="UA456",
            direction="D",
            location_iata="LAX",
            location_en="Los Angeles",
            location_he="לוס אנג'לס",
            location_city_en="Los Angeles",
            country_en="United States",
            country_he="ארצות הברית",
            airline_name="United Airlines",
            scheduled_time=now + timedelta(hours=3),
            actual_time=None,
            delay_minutes=0,
            terminal="1",
            checkin_counters="11-20",
            checkin_zone="B",
            status_en="On Time",
            status_he="בזמן",
            scrape_timestamp=now,
            raw_s3_path="s3://bucket/path/to/file3.json"
        ),
        Flight(
            flight_id="test-flight-4",
            airline_code="LY",
            flight_number="LY002",
            direction="A",
            location_iata="LHR",
            location_en="London",
            location_he="לונדון",
            location_city_en="London",
            country_en="United Kingdom",
            country_he="בריטניה",
            airline_name="El Al",
            scheduled_time=now - timedelta(hours=1),
            actual_time=now - timedelta(hours=1),
            delay_minutes=0,
            terminal="3",
            checkin_counters=None,
            checkin_zone=None,
            status_en="Landed",
            status_he="נחת",
            scrape_timestamp=now,
            raw_s3_path="s3://bucket/path/to/file4.json"
        ),
        Flight(
            flight_id="test-flight-5",
            airline_code="AA",
            flight_number="AA789",
            direction="D",
            location_iata="MIA",
            location_en="Miami",
            location_he="מיאמי",
            location_city_en="Miami",
            country_en="United States",
            country_he="ארצות הברית",
            airline_name="American Airlines",
            scheduled_time=now + timedelta(hours=4),
            actual_time=None,
            delay_minutes=0,
            terminal="1",
            checkin_counters="21-30",
            checkin_zone="C",
            status_en="On Time",
            status_he="בזמן",
            scrape_timestamp=now,
            raw_s3_path="s3://bucket/path/to/file5.json"
        ),
    ]
    
    db_session.add_all(flights)
    db_session.commit()
    
    return flights
