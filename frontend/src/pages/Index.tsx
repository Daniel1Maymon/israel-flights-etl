import { useState } from "react";
import { AirlineTable } from "@/components/AirlineTable";
import { DashboardFilters } from "@/components/DashboardFilters";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LanguageToggle } from "@/components/LanguageToggle";
import { DatabaseToggle } from "@/components/DatabaseToggle";
import { DynamicTable } from "@/components/DynamicTable";
import { PaginatedFlightsTable } from "@/components/PaginatedFlightsTable";
import { useLanguage } from "@/contexts/LanguageContext";
import { useApiData } from "@/hooks/useApiData";
import { usePaginatedFlights } from "@/hooks/usePaginatedFlights";
import { filterAirlinesByDestination, getTopAirlines, getBottomAirlines } from "@/lib/mockData.ts";
import { Plane, BarChart3 } from "lucide-react";
import { API_ENDPOINTS } from "@/config/api";

const Index = () => {
  const [selectedDestination, setSelectedDestination] = useState("All");
  const [selectedDateRange, setSelectedDateRange] = useState("all-time");
  const [selectedDayOfWeek, setSelectedDayOfWeek] = useState("all-days");
  const [selectedAirline, setSelectedAirline] = useState("All");
  const [isDatabaseMode, setIsDatabaseMode] = useState(false);
  const { t, isRTL } = useLanguage();
  
  // Helper function to build query parameters
  const buildQueryParams = () => {
    const params = new URLSearchParams();
    if (selectedDestination !== 'All') {
      params.append('destination', selectedDestination);
    }
    if (selectedDateRange !== 'all-time') {
      params.append('date_range', selectedDateRange);
    }
    if (selectedDayOfWeek !== 'all-days') {
      params.append('day_of_week', selectedDayOfWeek);
    }
    if (selectedAirline !== 'All') {
      params.append('airline', selectedAirline);
    }
    return params.toString();
  };

  // API endpoints
  const FLIGHTS_API_ENDPOINT = isDatabaseMode ? `${API_ENDPOINTS.FLIGHTS}/` : '';
  const AIRLINES_API_ENDPOINT = `${API_ENDPOINTS.AIRLINES_STATS}${buildQueryParams() ? `?${buildQueryParams()}` : ''}`;
  const AIRLINE_DESTINATIONS_ENDPOINT = selectedAirline !== 'All' 
    ? `${API_ENDPOINTS.AIRLINE_DESTINATIONS(selectedAirline)}${buildQueryParams() ? `?${buildQueryParams()}` : ''}`
    : '';
  
  // Fetch flight data from API when in database mode
  const { data: apiData, loading, error } = useApiData(FLIGHTS_API_ENDPOINT);
  
  // Fetch airline performance data (always use real data for airline tables)
  const { data: airlineData, loading: airlineLoading, error: airlineError } = useApiData(AIRLINES_API_ENDPOINT);
  
  
  // Fetch airline destinations data when an airline is selected
  const { data: airlineDestinationsData, loading: airlineDestinationsLoading, error: airlineDestinationsError } = useApiData(AIRLINE_DESTINATIONS_ENDPOINT);
  
  // Fetch paginated flight data when in database mode
  const {
    data: flightData,
    pagination,
    loading: flightsLoading,
    error: flightsError,
    goToPage,
    changePageSize,
    sortBy,
    currentPage,
    pageSize,
    sortField,
    sortDirection
  } = usePaginatedFlights(FLIGHTS_API_ENDPOINT);
  
  // Convert API data to mock format for AirlineTable component
  const convertToMockFormat = (airlines: any[]): any[] => {
    if (!Array.isArray(airlines) || airlines.length === 0) {
      return [];
    }
    
    const result = airlines
      .filter(airline => airline && airline.airline_name) // Filter out invalid entries
      .map((airline, index) => {
        return {
          airline: airline.airline_name || `Unknown-${index}`, // Use index to make keys unique
          onTimePercentage: airline.on_time_percentage || 0,
          avgDelayMinutes: airline.avg_delay_minutes || 0,
          cancellationPercentage: airline.cancellation_percentage || 0,
          flightCount: airline.total_flights || 0,
          destinations: [] // We don't have this in our current API
        };
      });
    return result;
  };

  // Convert airline destinations data to mock format for AirlineTable component
  const convertDestinationsToMockFormat = (destinations: any[]): any[] => {
    if (!Array.isArray(destinations) || destinations.length === 0) {
      return [];
    }
    
    return destinations
      .filter(destination => destination && destination.destination && destination.destination.trim() !== '') // Filter out invalid and empty entries
      .map((destination, index) => ({
        airline: destination.destination.trim() || `Unknown-${index}`, // Use trimmed destination name
        onTimePercentage: destination.on_time_percentage || 0,
        avgDelayMinutes: destination.avg_delay_minutes || 0,
        cancellationPercentage: destination.cancellation_percentage || 0,
        flightCount: destination.total_flights || 0,
        destinations: []
      }));
  };
  
  // Use real data for airline tables, fallback to mock data
  const realAirlines = Array.isArray(airlineData) ? airlineData : (airlineData as any)?.airlines || [];
  
  
  
  // Determine which data to use based on airline selection
  const isAirlineView = selectedAirline !== 'All';
  
  // If airline is selected, use destinations data; otherwise use airlines data
  const displayData = isAirlineView 
    ? ((airlineDestinationsData as any)?.destinations || [])
    : (realAirlines.length > 0 ? realAirlines : filterAirlinesByDestination(selectedDestination));
  
  // For stats panel - use airlines data
  const statsData = realAirlines.length > 0 ? realAirlines : filterAirlinesByDestination(selectedDestination);
  
  // Convert data to mock format for AirlineTable components
  const allAirlines = isAirlineView
    ? convertDestinationsToMockFormat(displayData)
    : convertToMockFormat(displayData);
  
  // Debug converted data

  return (
    <div className="min-h-screen bg-background" dir={isRTL ? 'rtl' : 'ltr'}>
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 p-3 bg-gradient-to-r from-primary to-info rounded-lg shadow-[var(--shadow-glow)]">
              <Plane className="h-6 w-6 text-primary-foreground" />
              <BarChart3 className="h-6 w-6 text-primary-foreground" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-foreground">
                {t('dashboard.title')}
              </h1>
              <p className="text-muted-foreground">
                {t('dashboard.subtitle')}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <DatabaseToggle 
              isDatabaseMode={isDatabaseMode}
              onToggle={() => setIsDatabaseMode(!isDatabaseMode)}
            />
            <LanguageToggle />
            <ThemeToggle />
          </div>
        </div>

        {/* Stats Panel */}
        <div className="mb-8 grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="bg-card border border-border rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-primary">
              {(airlineData as any)?.total_airlines || statsData.length}
            </div>
            <div className="text-sm text-muted-foreground">{t('airline.total')}</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-success">
              {realAirlines.length > 0 
                ? (airlineData as any)?.total_flights?.toLocaleString() || realAirlines.reduce((sum: number, airline: any) => sum + airline.total_flights, 0).toLocaleString()
                : statsData.reduce((sum, airline) => sum + airline.flightCount, 0).toLocaleString()
              }
            </div>
            <div className="text-sm text-muted-foreground">{t('airline.totalFlights')}</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-info">
              {realAirlines.length > 0 
                ? (realAirlines.reduce((sum: number, airline: any) => sum + airline.on_time_percentage, 0) / realAirlines.length).toFixed(1)
                : (statsData.reduce((sum, airline) => sum + airline.onTimePercentage, 0) / statsData.length).toFixed(1)
              }%
            </div>
            <div className="text-sm text-muted-foreground">{t('airline.avgOnTime')}</div>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-8">
          <DashboardFilters
            selectedDestination={selectedDestination}
            onDestinationChange={setSelectedDestination}
            selectedDateRange={selectedDateRange}
            onDateRangeChange={setSelectedDateRange}
            selectedDayOfWeek={selectedDayOfWeek}
            onDayOfWeekChange={setSelectedDayOfWeek}
            selectedAirline={selectedAirline}
            onAirlineChange={setSelectedAirline}
          />
        </div>

        {/* Tables */}
        {isDatabaseMode ? (
          <PaginatedFlightsTable
            data={flightData}
            pagination={pagination}
            loading={flightsLoading}
            error={flightsError}
            onPageChange={goToPage}
            onPageSizeChange={changePageSize}
            onSort={sortBy}
            currentPage={currentPage}
            pageSize={pageSize}
            sortField={sortField}
            sortDirection={sortDirection}
          />
        ) : (
          selectedAirline !== 'All' ? (
            // Single table view for selected airline's destinations
            <div className="max-h-screen overflow-hidden">
              <AirlineTable
                data={allAirlines}
                isTop={true}
                isAirlineView={true}
                airlineName={selectedAirline}
              />
            </div>
          ) : (
            // Two table view for top/bottom airlines (when no specific airline selected)
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 max-h-screen overflow-hidden">
              <div className="flex-shrink-0">
                <AirlineTable
                  data={allAirlines}
                  isTop={true}
                />
              </div>
              <div className="flex-shrink-0">
                <AirlineTable
                  data={allAirlines}
                  isTop={false}
                />
              </div>
            </div>
          )
        )}
      </div>
    </div>
  );
};

export default Index;