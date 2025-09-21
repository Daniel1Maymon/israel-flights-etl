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
import { filterAirlinesByDestination, getTopAirlines, getBottomAirlines } from "@/lib/mockData";
import { Plane, BarChart3 } from "lucide-react";

const Index = () => {
  const [selectedDestination, setSelectedDestination] = useState("All");
  const [selectedDateRange, setSelectedDateRange] = useState("all-time");
  const [selectedDayOfWeek, setSelectedDayOfWeek] = useState("all-days");
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
    return params.toString();
  };

  // API endpoints
  const FLIGHTS_API_ENDPOINT = isDatabaseMode ? 'http://localhost:8000/api/v1/flights/' : '';
  const AIRLINES_API_ENDPOINT = `http://localhost:8000/api/v1/airlines/stats${buildQueryParams() ? `?${buildQueryParams()}` : ''}`;
  
  // Fetch flight data from API when in database mode
  const { data: apiData, loading, error } = useApiData(FLIGHTS_API_ENDPOINT);
  
  // Fetch airline performance data (always use real data for airline tables)
  const { data: airlineData, loading: airlineLoading, error: airlineError } = useApiData(AIRLINES_API_ENDPOINT);
  
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
    return airlines.map(airline => ({
      airline: airline.airline_name, // Changed from 'name' to 'airline'
      onTimePercentage: airline.on_time_percentage,
      avgDelayMinutes: airline.avg_delay_minutes,
      cancellationPercentage: airline.cancellation_percentage,
      flightCount: airline.total_flights,
      destinations: [] // We don't have this in our current API
    }));
  };
  
  // Use real data for airline tables, fallback to mock data
  const realAirlines = airlineData || [];
  
  // Backend now handles all filtering, so we just use the data as-is
  const filteredData = realAirlines.length > 0 ? realAirlines : filterAirlinesByDestination(selectedDestination);
  
  // Sort airlines by on-time percentage (best to worst) for proper top/bottom separation
  const sortedAirlines = realAirlines.length > 0 
    ? [...realAirlines].sort((a, b) => b.on_time_percentage - a.on_time_percentage)
    : filterAirlinesByDestination(selectedDestination);
  
  const topAirlines = realAirlines.length > 0 
    ? convertToMockFormat(sortedAirlines.slice(0, 5))
    : getTopAirlines(filterAirlinesByDestination(selectedDestination), 5);
  const bottomAirlines = realAirlines.length > 0 
    ? convertToMockFormat(sortedAirlines.slice(-5))
    : getBottomAirlines(filterAirlinesByDestination(selectedDestination), 5);

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
              {realAirlines.length > 0 ? realAirlines.length : filteredData.length}
            </div>
            <div className="text-sm text-muted-foreground">{t('airline.total')}</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-success">
              {realAirlines.length > 0 
                ? realAirlines.reduce((sum: number, airline: any) => sum + airline.total_flights, 0).toLocaleString()
                : filteredData.reduce((sum, airline) => sum + airline.flightCount, 0).toLocaleString()
              }
            </div>
            <div className="text-sm text-muted-foreground">{t('airline.totalFlights')}</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-info">
              {realAirlines.length > 0 
                ? (realAirlines.reduce((sum: number, airline: any) => sum + airline.on_time_percentage, 0) / realAirlines.length).toFixed(1)
                : (filteredData.reduce((sum, airline) => sum + airline.onTimePercentage, 0) / filteredData.length).toFixed(1)
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
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            <AirlineTable
              data={topAirlines}
              isTop={true}
            />
            <AirlineTable
              data={bottomAirlines}
              isTop={false}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default Index;