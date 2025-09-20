from sqlalchemy import Column, String, Integer, DateTime, Text
from sqlalchemy.dialects.postgresql import TIMESTAMP
from app.database import Base


class Flight(Base):
    __tablename__ = "flights"
    
    # Primary key
    flight_id = Column(String(32), primary_key=True, index=True)
    
    # Flight information
    airline_code = Column(String(10), index=True)
    flight_number = Column(String(20), index=True)
    direction = Column(String(1), index=True)  # 'A' for arrival, 'D' for departure
    
    # Location information
    location_iata = Column(String(10), index=True)
    location_en = Column(String(100))
    location_he = Column(String(100))
    location_city_en = Column(String(100))
    country_en = Column(String(100))
    country_he = Column(String(100))
    
    # Airline information
    airline_name = Column(String(100))
    
    # Timing information
    scheduled_time = Column(TIMESTAMP(timezone=True), index=True)
    actual_time = Column(TIMESTAMP(timezone=True), index=True)
    delay_minutes = Column(Integer, index=True)
    
    # Terminal information
    terminal = Column(String(10), index=True)
    checkin_counters = Column(String(100))
    checkin_zone = Column(String(100))
    
    # Status information
    status_en = Column(String(100), index=True)
    status_he = Column(String(100))
    
    # Metadata
    scrape_timestamp = Column(TIMESTAMP(timezone=True))
    raw_s3_path = Column(String(500))
    
    def __repr__(self):
        return f"<Flight(flight_id='{self.flight_id}', airline='{self.airline_code}', flight_number='{self.flight_number}')>"
