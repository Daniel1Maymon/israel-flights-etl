"""
Airline Data Aggregation Service

This service handles the complex aggregation of individual flight records
into airline-level Key Performance Indicators (KPIs).

Key Concepts for Junior Data Engineers:
1. Aggregation: Combining many individual records into summary statistics
2. Grouping: Organizing data by common attributes (airline, destination, etc.)
3. Calculation: Computing metrics like averages, percentages, and counts
4. Data Quality: Handling missing data, outliers, and edge cases
"""

from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, case, desc, asc
import time
import structlog

from app.models.flight import Flight
from app.schemas.airline import (
    AirlineKPI, 
    AirlineStatsResponse, 
    AirlineTopBottomResponse,
    AirlineFilterParams
)

logger = structlog.get_logger()


class AirlineAggregationService:
    """
    Service class for aggregating flight data into airline KPIs
    
    This class encapsulates all the business logic for:
    - Calculating airline performance metrics
    - Handling data quality issues
    - Filtering and sorting results
    - Caching aggregated data
    """
    
    def __init__(self, db_session: Session):
        """
        Initialize the aggregation service
        
        Args:
            db_session: Database session for querying flight data
        """
        self.db = db_session
        self.logger = logger.bind(service="airline_aggregation")
    
    def calculate_airline_kpis(
        self, 
        filters: Optional[AirlineFilterParams] = None,
        cache_duration_minutes: int = 15
    ) -> AirlineStatsResponse:
        """
        Calculate comprehensive airline KPIs from flight data
        
        This is the main method that orchestrates the entire aggregation process.
        
        Args:
            filters: Optional filters to apply before aggregation
            cache_duration_minutes: How long to cache results (default 15 minutes)
            
        Returns:
            AirlineStatsResponse: Complete airline statistics with metadata
        """
        start_time = time.time()
        self.logger.info("Starting airline KPI calculation", filters=filters)
        
        try:
            # Step 1: Build the base query with filters
            base_query = self._build_filtered_query(filters)
            
            # Step 2: Get the date range of the data
            date_range = self._get_date_range(base_query)
            
            # Step 3: Calculate airline-level aggregations
            airline_data = self._calculate_airline_aggregations(base_query)
            
            # Step 4: Calculate KPIs for each airline
            airline_kpis = []
            for airline in airline_data:
                kpi = self._calculate_single_airline_kpi(airline, base_query)
                if kpi:  # Only include airlines that meet minimum criteria
                    airline_kpis.append(kpi)
            
            # Step 5: Apply final filters and sorting
            filtered_kpis = self._apply_final_filters(airline_kpis, filters)
            
            # Step 6: Calculate total statistics
            total_flights = sum(kpi.total_flights for kpi in filtered_kpis)
            
            calculation_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            
            self.logger.info(
                "Airline KPI calculation completed",
                airlines_count=len(filtered_kpis),
                total_flights=total_flights,
                calculation_time_ms=calculation_time
            )
            
            return AirlineStatsResponse(
                airlines=filtered_kpis,
                total_airlines=len(filtered_kpis),
                total_flights=total_flights,
                date_range=date_range,
                calculation_timestamp=datetime.utcnow(),
                calculation_time_ms=calculation_time
            )
            
        except Exception as e:
            self.logger.error("Error calculating airline KPIs", error=str(e), exc_info=True)
            raise
    
    def get_top_bottom_airlines(
        self, 
        filters: Optional[AirlineFilterParams] = None,
        top_limit: int = 5,
        bottom_limit: int = 5
    ) -> AirlineTopBottomResponse:
        """
        Get top and bottom performing airlines based on on-time percentage
        
        This method is useful for creating leaderboards and identifying
        airlines that need improvement.
        
        Args:
            filters: Optional filters to apply
            top_limit: Number of top airlines to return
            bottom_limit: Number of bottom airlines to return
            
        Returns:
            AirlineTopBottomResponse: Top and bottom airlines with metadata
        """
        self.logger.info("Getting top/bottom airlines", top_limit=top_limit, bottom_limit=bottom_limit)
        
        # Get all airline KPIs
        stats_response = self.calculate_airline_kpis(filters)
        all_airlines = stats_response.airlines
        
        # Sort by on-time percentage (descending for top, ascending for bottom)
        sorted_airlines = sorted(all_airlines, key=lambda x: x.on_time_percentage, reverse=True)
        
        # Split into top and bottom
        top_airlines = sorted_airlines[:top_limit]
        bottom_airlines = sorted_airlines[-bottom_limit:]
        
        return AirlineTopBottomResponse(
            top_airlines=top_airlines,
            bottom_airlines=bottom_airlines,
            total_airlines=len(all_airlines),
            calculation_timestamp=datetime.utcnow()
        )
    
    def _build_filtered_query(self, filters: Optional[AirlineFilterParams]) -> Any:
        """
        Build a filtered SQLAlchemy query based on the provided filters
        
        This method constructs the base query that will be used for aggregation.
        It applies all the necessary WHERE clauses based on the filter parameters.
        
        Args:
            filters: Filter parameters to apply
            
        Returns:
            SQLAlchemy query object with filters applied
        """
        # Start with the base Flight model
        query = self.db.query(Flight)
        
        if not filters:
            return query
        
        # Apply date range filters
        if filters.date_from:
            query = query.filter(Flight.scheduled_time >= filters.date_from)
        if filters.date_to:
            query = query.filter(Flight.scheduled_time <= filters.date_to)
        
        # Apply destination filters
        if filters.destination:
            query = query.filter(
                or_(
                    Flight.location_en.ilike(f"%{filters.destination}%"),
                    Flight.location_he.ilike(f"%{filters.destination}%"),
                    Flight.location_city_en.ilike(f"%{filters.destination}%")
                )
            )
        
        if filters.country:
            query = query.filter(
                or_(
                    Flight.country_en.ilike(f"%{filters.country}%"),
                    Flight.country_he.ilike(f"%{filters.country}%")
                )
            )
        
        # Apply airline code filters
        if filters.airline_codes:
            query = query.filter(Flight.airline_code.in_(filters.airline_codes))
        
        return query
    
    def _get_date_range(self, query: Any) -> Dict[str, datetime]:
        """
        Get the date range of the filtered data
        
        This helps users understand what time period the statistics cover.
        
        Args:
            query: The filtered query to analyze
            
        Returns:
            Dictionary with 'start' and 'end' datetime values
        """
        # Get the earliest and latest scheduled times
        min_date = query.with_entities(func.min(Flight.scheduled_time)).scalar()
        max_date = query.with_entities(func.max(Flight.scheduled_time)).scalar()
        
        return {
            "start": min_date or datetime.utcnow(),
            "end": max_date or datetime.utcnow()
        }
    
    def _calculate_airline_aggregations(self, query: Any) -> List[Dict[str, Any]]:
        """
        Calculate basic aggregations for each airline
        
        This method performs the core SQL aggregation using GROUP BY.
        It calculates counts, averages, and other basic statistics for each airline.
        
        Args:
            query: The filtered query to aggregate
            
        Returns:
            List of dictionaries containing airline aggregation data
        """
        # Define the aggregation query
        # This is where the magic happens - we group by airline and calculate metrics
        aggregation_query = query.with_entities(
            # Group by airline information
            Flight.airline_code,
            Flight.airline_name,
            
            # Count total flights
            func.count(Flight.flight_id).label('total_flights'),
            
            # Count on-time flights (delay <= 0 or null)
            func.count(
                case(
                    (or_(Flight.delay_minutes <= 0, Flight.delay_minutes.is_(None)), 1),
                    else_=None
                )
            ).label('on_time_flights'),
            
            # Count delayed flights (delay > 0)
            func.count(
                case(
                    (Flight.delay_minutes > 0, 1),
                    else_=None
                )
            ).label('delayed_flights'),
            
            # Count cancelled flights
            func.count(
                case(
                    (or_(
                        Flight.status_en.ilike('%cancelled%'),
                        Flight.status_he.ilike('%בוטל%')
                    ), 1),
                    else_=None
                )
            ).label('cancelled_flights'),
            
            # Calculate average delay for delayed flights only
            func.avg(
                case(
                    (Flight.delay_minutes > 0, Flight.delay_minutes),
                    else_=None
                )
            ).label('avg_delay_delayed_only'),
            
            # Calculate average delay for all flights (including on-time)
            func.avg(
                case(
                    (Flight.delay_minutes.isnot(None), Flight.delay_minutes),
                    else_=0
                )
            ).label('avg_delay_all_flights'),
            
            # Get unique destinations (we'll process this separately)
            func.array_agg(
                func.distinct(Flight.location_en)
            ).label('destinations_raw')
        ).group_by(
            Flight.airline_code,
            Flight.airline_name
        )
        
        # Execute the query and process results
        # SECURITY: Apply limit to prevent data dump
        results = aggregation_query.limit(1000).all()
        
        # Convert SQLAlchemy Row objects to dictionaries
        airline_data = []
        for row in results:
            # Clean up destinations list (remove None values and duplicates)
            destinations = [d for d in (row.destinations_raw or []) if d and d.strip()]
            destinations = list(set(destinations))  # Remove duplicates
            
            airline_data.append({
                'airline_code': row.airline_code,
                'airline_name': row.airline_name,
                'total_flights': row.total_flights or 0,
                'on_time_flights': row.on_time_flights or 0,
                'delayed_flights': row.delayed_flights or 0,
                'cancelled_flights': row.cancelled_flights or 0,
                'avg_delay_delayed_only': float(row.avg_delay_delayed_only or 0),
                'avg_delay_all_flights': float(row.avg_delay_all_flights or 0),
                'destinations': destinations
            })
        
        return airline_data
    
    def _calculate_single_airline_kpi(self, airline_data: Dict[str, Any], base_query: Any) -> Optional[AirlineKPI]:
        """
        Calculate KPIs for a single airline
        
        This method takes the raw aggregation data and calculates the final KPIs.
        It handles edge cases and data quality issues.
        
        Args:
            airline_data: Raw aggregation data for one airline
            base_query: Base query for additional calculations if needed
            
        Returns:
            AirlineKPI object or None if airline doesn't meet minimum criteria
        """
        total_flights = airline_data['total_flights']
        
        # Skip airlines with too few flights (data quality issue)
        if total_flights < 1:
            return None
        
        # Calculate percentages
        on_time_percentage = (airline_data['on_time_flights'] / total_flights) * 100
        cancellation_percentage = (airline_data['cancelled_flights'] / total_flights) * 100
        
        # Calculate data quality score
        # This measures how complete the data is for this airline
        data_quality_score = self._calculate_data_quality_score(airline_data, base_query)
        
        # Create the KPI object
        kpi = AirlineKPI(
            airline_code=airline_data['airline_code'],
            airline_name=airline_data['airline_name'],
            on_time_percentage=round(on_time_percentage, 2),
            avg_delay_minutes=round(airline_data['avg_delay_delayed_only'], 2),
            cancellation_percentage=round(cancellation_percentage, 2),
            total_flights=total_flights,
            on_time_flights=airline_data['on_time_flights'],
            delayed_flights=airline_data['delayed_flights'],
            cancelled_flights=airline_data['cancelled_flights'],
            destinations=airline_data['destinations'],
            avg_delay_all_flights=round(airline_data['avg_delay_all_flights'], 2),
            data_quality_score=round(data_quality_score, 2),
            last_updated=datetime.utcnow()
        )
        
        return kpi
    
    def _calculate_data_quality_score(self, airline_data: Dict[str, Any], base_query: Any) -> float:
        """
        Calculate a data quality score for an airline
        
        This helps identify airlines with incomplete or unreliable data.
        A score of 100 means perfect data quality, 0 means very poor quality.
        
        Args:
            airline_data: Raw aggregation data for the airline
            base_query: Base query for additional quality checks
            
        Returns:
            Data quality score between 0 and 100
        """
        total_flights = airline_data['total_flights']
        if total_flights == 0:
            return 0.0
        
        # Check various data quality indicators
        quality_checks = []
        
        # 1. Check for missing delay data
        # We'll estimate this by checking if we have reasonable delay values
        avg_delay = airline_data['avg_delay_all_flights']
        if avg_delay is not None and avg_delay >= 0:
            quality_checks.append(1.0)  # Good delay data
        else:
            quality_checks.append(0.5)  # Some delay data missing
        
        # 2. Check for missing destination data
        destinations = airline_data['destinations']
        if len(destinations) > 0:
            quality_checks.append(1.0)  # Good destination data
        else:
            quality_checks.append(0.3)  # Missing destination data
        
        # 3. Check for reasonable flight counts
        # Very low or very high counts might indicate data issues
        if 1 <= total_flights <= 10000:  # Reasonable range
            quality_checks.append(1.0)
        elif total_flights > 10000:  # Very high, might be duplicate data
            quality_checks.append(0.8)
        else:  # Very low, might be incomplete data
            quality_checks.append(0.6)
        
        # 4. Check for missing airline name
        if airline_data['airline_name'] and airline_data['airline_name'].strip():
            quality_checks.append(1.0)
        else:
            quality_checks.append(0.5)
        
        # Calculate overall quality score
        return sum(quality_checks) / len(quality_checks) * 100
    
    def _apply_final_filters(self, airline_kpis: List[AirlineKPI], filters: Optional[AirlineFilterParams]) -> List[AirlineKPI]:
        """
        Apply final filters and sorting to the calculated KPIs
        
        This method handles the final filtering and sorting of results
        before returning them to the user.
        
        Args:
            airline_kpis: List of calculated airline KPIs
            filters: Filter parameters to apply
            
        Returns:
            Filtered and sorted list of airline KPIs
        """
        if not filters:
            return airline_kpis
        
        # Apply minimum flight count filter
        if filters.min_flights > 1:
            airline_kpis = [kpi for kpi in airline_kpis if kpi.total_flights >= filters.min_flights]
        
        # Apply minimum on-time percentage filter
        if filters.min_on_time_percentage is not None:
            airline_kpis = [kpi for kpi in airline_kpis if kpi.on_time_percentage >= filters.min_on_time_percentage]
        
        # Apply maximum average delay filter
        if filters.max_avg_delay is not None:
            airline_kpis = [kpi for kpi in airline_kpis if kpi.avg_delay_minutes <= filters.max_avg_delay]
        
        # Apply sorting
        reverse_order = filters.sort_order.lower() == 'desc'
        sort_field = filters.sort_by
        
        if sort_field == 'on_time_percentage':
            airline_kpis.sort(key=lambda x: x.on_time_percentage, reverse=reverse_order)
        elif sort_field == 'avg_delay_minutes':
            airline_kpis.sort(key=lambda x: x.avg_delay_minutes, reverse=reverse_order)
        elif sort_field == 'total_flights':
            airline_kpis.sort(key=lambda x: x.total_flights, reverse=reverse_order)
        elif sort_field == 'cancellation_percentage':
            airline_kpis.sort(key=lambda x: x.cancellation_percentage, reverse=reverse_order)
        else:
            # Default to on-time percentage
            airline_kpis.sort(key=lambda x: x.on_time_percentage, reverse=reverse_order)
        
        # Apply limit
        if filters.limit:
            airline_kpis = airline_kpis[:filters.limit]
        
        return airline_kpis
