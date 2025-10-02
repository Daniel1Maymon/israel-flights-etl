"""
Airline KPI schemas for aggregated flight data
This file defines the data structures for airline performance metrics
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class AirlineKPI(BaseModel):
    """
    Airline Key Performance Indicators (KPIs) schema
    
    This represents aggregated statistics for a single airline
    calculated from individual flight records.
    """
    
    # Basic airline information
    airline_code: str = Field(..., description="IATA airline code (e.g., 'DL', 'AA')")
    airline_name: str = Field(..., description="Full airline name (e.g., 'Delta Air Lines')")
    
    # Performance metrics
    on_time_percentage: float = Field(..., ge=0, le=100, description="Percentage of flights that arrived on time (0-100)")
    avg_delay_minutes: float = Field(..., ge=0, description="Average delay in minutes for delayed flights only")
    cancellation_percentage: float = Field(..., ge=0, le=100, description="Percentage of cancelled flights (0-100)")
    
    # Volume metrics
    total_flights: int = Field(..., ge=0, description="Total number of flights for this airline")
    on_time_flights: int = Field(..., ge=0, description="Number of flights that arrived on time")
    delayed_flights: int = Field(..., ge=0, description="Number of flights that were delayed")
    cancelled_flights: int = Field(..., ge=0, description="Number of cancelled flights")
    
    # Additional insights
    destinations: List[str] = Field(default_factory=list, description="List of unique destinations served")
    avg_delay_all_flights: float = Field(..., description="Average delay across ALL flights (including on-time)")
    
    # Data quality metrics
    data_quality_score: float = Field(..., ge=0, le=100, description="Data completeness score (0-100)")
    last_updated: datetime = Field(..., description="When this KPI was last calculated")


class AirlineStatsResponse(BaseModel):
    """
    Response schema for airline statistics endpoint
    
    Contains aggregated airline KPIs and metadata about the calculation
    """
    
    # The main data
    airlines: List[AirlineKPI] = Field(..., description="List of airline KPIs")
    
    # Metadata about the aggregation
    total_airlines: int = Field(..., description="Total number of airlines in the dataset")
    total_flights: int = Field(..., description="Total number of flights across all airlines")
    date_range: Dict[str, datetime] = Field(..., description="Start and end dates of the data")
    calculation_timestamp: datetime = Field(..., description="When the aggregation was performed")
    
    # Performance metrics
    calculation_time_ms: float = Field(..., description="Time taken to calculate the aggregation in milliseconds")


class AirlineTopBottomResponse(BaseModel):
    """
    Response schema for top/bottom performing airlines
    
    Separates airlines into top and bottom performers based on on-time percentage
    """
    
    top_airlines: List[AirlineKPI] = Field(..., description="Top performing airlines (highest on-time %)")
    bottom_airlines: List[AirlineKPI] = Field(..., description="Bottom performing airlines (lowest on-time %)")
    
    # Metadata
    total_airlines: int = Field(..., description="Total number of airlines analyzed")
    calculation_timestamp: datetime = Field(..., description="When the analysis was performed")


class AirlineFilterParams(BaseModel):
    """
    Parameters for filtering airline statistics
    
    Allows filtering by various criteria before aggregation
    """
    
    # Date range filtering
    date_from: Optional[datetime] = Field(None, description="Start date for filtering flights")
    date_to: Optional[datetime] = Field(None, description="End date for filtering flights")
    
    # Destination filtering
    destination: Optional[str] = Field(None, description="Filter by specific destination")
    country: Optional[str] = Field(None, description="Filter by specific country")
    
    # Airline filtering
    airline_codes: Optional[List[str]] = Field(None, description="Filter by specific airline codes")
    
    # Performance filtering
    min_flights: int = Field(1, ge=1, description="Minimum number of flights required for inclusion")
    min_on_time_percentage: Optional[float] = Field(None, ge=0, le=100, description="Minimum on-time percentage")
    max_avg_delay: Optional[float] = Field(None, ge=0, description="Maximum average delay in minutes")
    
    # Sorting options
    sort_by: str = Field("on_time_percentage", description="Field to sort by")
    sort_order: str = Field("desc", description="Sort order: 'asc' or 'desc'")
    limit: Optional[int] = Field(None, ge=1, le=1000, description="Maximum number of airlines to return")
