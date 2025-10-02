/**
 * Custom hook for fetching airline performance data
 * 
 * This hook replaces the mock data with real airline KPIs from the backend API.
 * It handles loading states, errors, and data transformation.
 */

import { useState, useEffect } from 'react';

// Define the interface for airline KPI data from the backend
interface AirlineKPI {
  airline_code: string;
  airline_name: string;
  on_time_percentage: number;
  avg_delay_minutes: number;
  cancellation_percentage: number;
  total_flights: number;
  on_time_flights: number;
  delayed_flights: number;
  cancelled_flights: number;
  destinations: string[];
  avg_delay_all_flights: number;
  data_quality_score: number;
  last_updated: string;
}

// Define the response structure from the API
interface AirlineStatsResponse {
  airlines: AirlineKPI[];
  total_airlines: number;
  total_flights: number;
  date_range: {
    start: string;
    end: string;
  };
  calculation_timestamp: string;
  calculation_time_ms: number;
}

// Define the hook's return type
interface UseAirlineDataResult {
  data: AirlineKPI[];
  loading: boolean;
  error: string | null;
  refetch: () => void;
  totalAirlines: number;
  totalFlights: number;
  dateRange: { start: string; end: string } | null;
  calculationTime: number | null;
}

/**
 * Custom hook for fetching airline performance data
 * 
 * @param endpoint - The API endpoint to fetch data from
 * @returns Object containing data, loading state, error state, and refetch function
 */
export const useAirlineData = (endpoint: string): UseAirlineDataResult => {
  // State management
  const [data, setData] = useState<AirlineKPI[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [totalAirlines, setTotalAirlines] = useState(0);
  const [totalFlights, setTotalFlights] = useState(0);
  const [dateRange, setDateRange] = useState<{ start: string; end: string } | null>(null);
  const [calculationTime, setCalculationTime] = useState<number | null>(null);

  /**
   * Fetch data from the API endpoint
   * This function handles the HTTP request and data transformation
   */
  const fetchData = async () => {
    // Don't fetch if no endpoint is provided (mock data mode)
    if (!endpoint) {
      setData([]);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    
    try {
      console.log('Fetching airline data from:', endpoint);
      
      // Make the HTTP request
      const response = await fetch(endpoint);
      
      // Check if the response is successful
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      // Parse the JSON response
      const result: AirlineStatsResponse = await response.json();
      
      console.log('Received airline data:', result);
      
      // Validate the response structure
      if (!result.airlines || !Array.isArray(result.airlines)) {
        throw new Error('Invalid response format: missing or invalid airlines array');
      }
      
      // Transform the data to match the frontend interface
      const transformedData = result.airlines.map(airline => ({
        ...airline,
        // Ensure all required fields are present with fallback values
        on_time_percentage: airline.on_time_percentage || 0,
        avg_delay_minutes: airline.avg_delay_minutes || 0,
        cancellation_percentage: airline.cancellation_percentage || 0,
        total_flights: airline.total_flights || 0,
        on_time_flights: airline.on_time_flights || 0,
        delayed_flights: airline.delayed_flights || 0,
        cancelled_flights: airline.cancelled_flights || 0,
        destinations: airline.destinations || [],
        avg_delay_all_flights: airline.avg_delay_all_flights || 0,
        data_quality_score: airline.data_quality_score || 0,
        last_updated: airline.last_updated || new Date().toISOString()
      }));
      
      // Update state with the fetched data
      setData(transformedData);
      setTotalAirlines(result.total_airlines || 0);
      setTotalFlights(result.total_flights || 0);
      setDateRange(result.date_range || null);
      setCalculationTime(result.calculation_time_ms || null);
      
      console.log('Successfully loaded airline data:', {
        airlinesCount: transformedData.length,
        totalAirlines: result.total_airlines,
        totalFlights: result.total_flights
      });
      
    } catch (err) {
      // Handle errors gracefully
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred';
      console.error('Error fetching airline data:', errorMessage);
      
      setError(`Failed to fetch airline data: ${errorMessage}`);
      setData([]);
      setTotalAirlines(0);
      setTotalFlights(0);
      setDateRange(null);
      setCalculationTime(null);
    } finally {
      setLoading(false);
    }
  };

  // Effect to fetch data when the endpoint changes
  useEffect(() => {
    fetchData();
  }, [endpoint]);

  // Return the hook's interface
  return {
    data,
    loading,
    error,
    refetch: fetchData,
    totalAirlines,
    totalFlights,
    dateRange,
    calculationTime
  };
};

/**
 * Custom hook for fetching top and bottom performing airlines
 * 
 * This hook fetches the best and worst performing airlines separately,
 * which is useful for creating leaderboards.
 */
export const useTopBottomAirlines = (endpoint: string) => {
  const [topAirlines, setTopAirlines] = useState<AirlineKPI[]>([]);
  const [bottomAirlines, setBottomAirlines] = useState<AirlineKPI[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTopBottom = async () => {
    if (!endpoint) {
      setTopAirlines([]);
      setBottomAirlines([]);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${endpoint}/top-bottom`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const result = await response.json();
      
      setTopAirlines(result.top_airlines || []);
      setBottomAirlines(result.bottom_airlines || []);
      
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred';
      setError(`Failed to fetch top/bottom airlines: ${errorMessage}`);
      setTopAirlines([]);
      setBottomAirlines([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTopBottom();
  }, [endpoint]);

  return {
    topAirlines,
    bottomAirlines,
    loading,
    error,
    refetch: fetchTopBottom
  };
};
