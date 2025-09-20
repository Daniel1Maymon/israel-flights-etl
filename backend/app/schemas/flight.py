from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class FlightBase(BaseModel):
    """Base flight schema with common fields"""
    airline_code: str
    flight_number: str
    direction: str  # 'A' or 'D'
    location_iata: str
    scheduled_time: datetime
    actual_time: Optional[datetime] = None
    airline_name: str
    location_en: str
    location_he: str
    location_city_en: str
    country_en: str
    country_he: str
    terminal: Optional[str] = None
    checkin_counters: Optional[str] = None
    checkin_zone: Optional[str] = None
    status_en: str
    status_he: str
    delay_minutes: int = 0
    scrape_timestamp: Optional[datetime] = None
    raw_s3_path: str


class Flight(FlightBase):
    """Complete flight schema for responses"""
    flight_id: str
    
    model_config = ConfigDict(from_attributes=True)


class FlightCreate(FlightBase):
    """Schema for creating flights"""
    flight_id: str


class FlightUpdate(BaseModel):
    """Schema for updating flights"""
    actual_time: Optional[datetime] = None
    status_en: Optional[str] = None
    status_he: Optional[str] = None
    delay_minutes: Optional[int] = None
    scrape_timestamp: Optional[datetime] = None
    raw_s3_path: Optional[str] = None


class PaginationInfo(BaseModel):
    """Pagination metadata"""
    page: int
    size: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool


class FlightListResponse(BaseModel):
    """Response schema for flight list endpoints"""
    data: List[Flight]
    pagination: PaginationInfo


class FlightStats(BaseModel):
    """Statistics response schema"""
    total_flights: int
    on_time_flights: int
    delayed_flights: int
    average_delay: float
    by_airline: Optional[List[dict]] = None
    by_destination: Optional[List[dict]] = None
    by_hour: Optional[List[dict]] = None
    by_day: Optional[List[dict]] = None


class AirlineInfo(BaseModel):
    """Airline information schema"""
    airline_code: str
    airline_name: str
    flight_count: int


class DestinationInfo(BaseModel):
    """Destination information schema"""
    location_iata: str
    location_en: str
    location_he: str
    location_city_en: str
    country_en: str
    country_he: str
    flight_count: int


class ErrorResponse(BaseModel):
    """Error response schema"""
    error: dict = Field(..., description="Error details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid input parameters",
                    "details": {"field": "page", "issue": "Must be positive integer"}
                }
            }
        }
