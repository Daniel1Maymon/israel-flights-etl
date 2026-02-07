import { useState, useMemo } from "react";
import { AirlineTable } from "@/components/AirlineTable";
import { DashboardFilters } from "@/components/DashboardFilters";
import { AirlinePerformanceCard } from "@/components/AirlinePerformanceCard";
import { ThemeToggle } from "@/components/ThemeToggle";
import { LanguageToggle } from "@/components/LanguageToggle";
import { DatabaseToggle } from "@/components/DatabaseToggle";
import { DynamicTable } from "@/components/DynamicTable";
import { PaginatedFlightsTable } from "@/components/PaginatedFlightsTable";
import { useLanguage } from "@/contexts/LanguageContext";
import { useApiData } from "@/hooks/useApiData";
import { useAirlineData, type AirlineBackendKPI } from "@/hooks/useAirlineData";
import { usePaginatedFlights } from "@/hooks/usePaginatedFlights";
import { filterAirlinesByDestination, getTopAirlines, getBottomAirlines, type AirlineKPI } from "@/lib/mockData.ts";
import { Plane, BarChart3, Github, Linkedin } from "lucide-react";
import { API_ENDPOINTS } from "@/config/api";

type SearchType = "airline" | "airport" | "country" | "city";

type AirlineDestinationKPI = {
  destination?: string;
  on_time_percentage?: number;
  avg_delay_all_flights?: number;
  avg_delay_minutes?: number;
  cancellation_percentage?: number;
  total_flights?: number;
};

const Index = () => {
  const [selectedAirport, setSelectedAirport] = useState("All");
  const [selectedAirline, setSelectedAirline] = useState("All");
  const [selectedSearch, setSelectedSearch] = useState("All");
  const [selectedSearchType, setSelectedSearchType] = useState<SearchType>("airport");
  const [selectedDateRange, setSelectedDateRange] = useState("all-time");
  const [topLimit, setTopLimit] = useState(5);
  const [isDatabaseMode, setIsDatabaseMode] = useState(false);
  const [resetSignal, setResetSignal] = useState(0);
  const { t, isRTL } = useLanguage();
  
  // Fetch airlines to build name-to-code mapping
  const { data: airlinesData } = useApiData(API_ENDPOINTS.AIRLINES);
  const airlineNameToCodeMap = useMemo(() => {
    const map = new Map<string, string>();
    if (airlinesData && airlinesData.length > 0) {
      airlinesData.forEach((airline: Record<string, unknown>) => {
        const name = airline.airline_name || airline.name;
        const code = airline.airline_code || airline.code;
        if (name && code) {
          map.set(name as string, code as string);
        }
      });
    }
    return map;
  }, [airlinesData]);
  
  // Helper function to build query parameters for airline stats API
  // Backend expects: destination, country, date_from, date_to, airline_codes
  const buildQueryParams = () => {
    const params = new URLSearchParams();
    
    // Handle airport filter (from dropdown)
    if (selectedAirport !== 'All') {
      params.append('destination', selectedAirport);
    }
    
    // Handle search filter (from unified search bar)
    // Only process if not already handled by dropdowns
    if (selectedSearch !== 'All') {
      if (selectedSearchType === 'country') {
        // Country from search bar
        params.append('country', selectedSearch);
      } else if (selectedSearchType === 'airport' && selectedAirport === 'All') {
        // Airport from search bar (only if dropdown airport is not set)
        params.append('destination', selectedSearch);
      } else if (selectedSearchType === 'airline') {
        // Airline from search bar (takes priority over dropdown)
        const airlineCode = airlineNameToCodeMap.get(selectedSearch);
        if (airlineCode) {
          params.append('airline_codes', airlineCode);
        }
      }
      // Note: city filtering would need backend support
    }
    
    // Handle airline filter (from dropdown) - only if search doesn't already have airline
    if (selectedAirline !== 'All' && selectedSearchType !== 'airline') {
      const airlineCode = airlineNameToCodeMap.get(selectedAirline);
      if (airlineCode) {
        params.append('airline_codes', airlineCode);
      }
    }
    
    // Convert date_range to date_from and date_to
    if (selectedDateRange !== 'all-time') {
      const now = new Date();
      let dateFrom: Date;
      const dateTo: Date = now;
      
      switch (selectedDateRange) {
        case 'last-7-days':
          dateFrom = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
          break;
        case 'last-30-days':
          dateFrom = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
          break;
        case 'last-90-days':
          dateFrom = new Date(now.getTime() - 90 * 24 * 60 * 60 * 1000);
          break;
        case 'last-year':
          dateFrom = new Date(now.getTime() - 365 * 24 * 60 * 60 * 1000);
          break;
        default:
          dateFrom = new Date(0); // Beginning of time
      }
      
      params.append('date_from', dateFrom.toISOString());
      params.append('date_to', dateTo.toISOString());
    }
    
    return params.toString();
  };
  
  // Handle search value change
  const handleSearchChange = (value: string, type: SearchType) => {
    setSelectedSearch(value);
    setSelectedSearchType(type);
  };

  const handleResetFilters = () => {
    setSelectedAirport("All");
    setSelectedAirline("All");
    setSelectedSearch("All");
    setSelectedSearchType("airport");
    setSelectedDateRange("all-time");
    setTopLimit(5);
    setResetSignal((prev) => prev + 1);
  };

  // Determine effective filters (priority: search bar > dropdowns)
  // Priority: search bar airline > dropdown airline
  const effectiveAirline = selectedSearchType === 'airline' && selectedSearch !== 'All' 
    ? selectedSearch 
    : selectedAirline;
  
  // Priority: dropdown airport > search bar airport
  const effectiveDestination = selectedAirport !== 'All' 
    ? selectedAirport 
    : (selectedSearchType === 'airport' && selectedSearch !== 'All' ? selectedSearch : null);

  // API endpoints
  const FLIGHTS_API_ENDPOINT = isDatabaseMode ? API_ENDPOINTS.FLIGHTS : '';
  const AIRLINES_API_ENDPOINT = `${API_ENDPOINTS.AIRLINES_STATS}${buildQueryParams() ? `?${buildQueryParams()}` : ''}`;
  // Convert airline name to code for airline-specific destinations endpoint
  const getAirlineCode = (airlineName: string): string => {
    return airlineNameToCodeMap.get(airlineName) || airlineName;
  };
  
  const destinationsQuery = (() => {
    const params = new URLSearchParams(buildQueryParams());
    params.set('lang', isRTL ? 'he' : 'en');
    return params.toString();
  })();

  const AIRLINE_DESTINATIONS_ENDPOINT = effectiveAirline !== 'All' 
    ? `${API_ENDPOINTS.AIRLINE_DESTINATIONS(getAirlineCode(effectiveAirline))}${destinationsQuery ? `?${destinationsQuery}` : ''}`
    : '';
  
  // Fetch flight data from API when in database mode
  const { data: apiData, loading, error } = useApiData(FLIGHTS_API_ENDPOINT);
  
  // Fetch airline performance data (use backend totals, not frontend-derived sums)
  const {
    data: airlineData,
    loading: airlineLoading,
    error: airlineError,
    totalAirlines,
    totalFlights
  } = useAirlineData(AIRLINES_API_ENDPOINT);
  
  
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
  const convertToMockFormat = (airlines: AirlineBackendKPI[]): AirlineKPI[] => {
    if (!Array.isArray(airlines) || airlines.length === 0) {
      return [];
    }
    
    const result = airlines
      .filter(airline => airline && airline.airline_name) // Filter out invalid entries
      .map((airline, index) => {
        return {
          airline: airline.airline_name || `Unknown-${index}`, // Use index to make keys unique
          onTimePercentage: airline.on_time_percentage || 0,
          // Use avg_delay_all_flights (includes on-time flights as 0) instead of avg_delay_minutes (delayed only)
          // This gives a more intuitive overall performance metric
          avgDelayMinutes: airline.avg_delay_all_flights ?? airline.avg_delay_minutes ?? 0,
          cancellationPercentage: airline.cancellation_percentage || 0,
          flightCount: airline.total_flights || 0,
          destinations: [] // We don't have this in our current API
        };
      });
    return result;
  };

  // Convert airline destinations data to mock format for AirlineTable component
  const convertDestinationsToMockFormat = (destinations: AirlineDestinationKPI[]): AirlineKPI[] => {
    if (!Array.isArray(destinations) || destinations.length === 0) {
      return [];
    }
    
    return destinations
      .filter(destination => destination && destination.destination && destination.destination.trim() !== '') // Filter out invalid and empty entries
      .map((destination, index) => ({
        airline: destination.destination.trim() || `Unknown-${index}`, // Use trimmed destination name
        onTimePercentage: destination.on_time_percentage || 0,
        // Use avg_delay_all_flights if available (includes on-time flights as 0), fallback to avg_delay_minutes
        avgDelayMinutes: destination.avg_delay_all_flights ?? destination.avg_delay_minutes ?? 0,
        cancellationPercentage: destination.cancellation_percentage || 0,
        flightCount: destination.total_flights || 0,
        destinations: []
      }));
  };
  
  // Use real data for airline tables, fallback to mock data
  const realAirlines = useMemo<AirlineBackendKPI[]>(
    () => (Array.isArray(airlineData) ? airlineData : []),
    [airlineData]
  );

  const isAirlineView = effectiveAirline !== 'All' && !effectiveDestination;
  const isDestinationView = effectiveDestination && effectiveAirline !== 'All';

  // Get single airline performance data when only airline is selected
  const singleAirlineData = useMemo(() => {
    if (isAirlineView && realAirlines.length > 0) {
      return realAirlines.find((airline) =>
        airline.airline_name === effectiveAirline ||
        airline.airline_code === airlineNameToCodeMap.get(effectiveAirline)
      );
    }
    return null;
  }, [isAirlineView, realAirlines, effectiveAirline, airlineNameToCodeMap]);
  
  const airlineDestinationsArray: AirlineDestinationKPI[] = Array.isArray(airlineDestinationsData)
    ? (airlineDestinationsData as AirlineDestinationKPI[])
    : (Array.isArray((airlineDestinationsData as Record<string, unknown>)?.destinations)
        ? ((airlineDestinationsData as Record<string, unknown>).destinations as AirlineDestinationKPI[])
        : []);

  const mockFallback = filterAirlinesByDestination(effectiveDestination || 'All');
  
  // Convert data to mock format for AirlineTable components
  const allAirlines: AirlineKPI[] = isDestinationView
    ? convertDestinationsToMockFormat(airlineDestinationsArray)
    : (realAirlines.length > 0 ? convertToMockFormat(realAirlines) : mockFallback);
  
  // For stats panel - use mock-format data so fields are consistent
  const statsData: AirlineKPI[] = realAirlines.length > 0 ? convertToMockFormat(realAirlines) : mockFallback;
  
  // Filter airlines to only show those with at least 20 flights
  const filteredAirlines = allAirlines.filter(airline => airline.flightCount >= 20);

  const airlineDestinations = convertDestinationsToMockFormat(airlineDestinationsArray);
  
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
              {realAirlines.length > 0 ? totalAirlines : statsData.length}
            </div>
            <div className="text-sm text-muted-foreground">{t('airline.total')}</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-success">
              {realAirlines.length > 0 
                ? totalFlights.toLocaleString()
                : statsData.reduce((sum, airline) => sum + airline.flightCount, 0).toLocaleString()
              }
            </div>
            <div className="text-sm text-muted-foreground">{t('airline.totalFlights')}</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-info">
              {realAirlines.length > 0
                ? (realAirlines.reduce((sum, airline) => sum + airline.on_time_percentage, 0) / realAirlines.length).toFixed(1)
                : (statsData.reduce((sum, airline) => sum + airline.onTimePercentage, 0) / statsData.length).toFixed(1)
              }%
            </div>
            <div className="text-sm text-muted-foreground">{t('airline.avgOnTime')}</div>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-8">
          <DashboardFilters
            selectedAirport={selectedAirport}
            onAirportChange={setSelectedAirport}
            selectedAirline={selectedAirline}
            onAirlineChange={setSelectedAirline}
            selectedSearch={selectedSearch}
            onSearchChange={handleSearchChange}
            selectedDateRange={selectedDateRange}
            onDateRangeChange={setSelectedDateRange}
            topLimit={topLimit}
            onTopLimitChange={setTopLimit}
            onReset={handleResetFilters}
            resetSignal={resetSignal}
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
          isAirlineView && singleAirlineData ? (
            // Single airline performance card when only airline is selected
            <div className="max-w-5xl mx-auto space-y-4">
              <AirlinePerformanceCard airline={singleAirlineData} />
              <AirlineTable
                data={airlineDestinations}
                isTop={true}
                isAirlineView={true}
                airlineName={effectiveAirline}
                limit={Math.max(airlineDestinations.length, 1)}
              />
            </div>
          ) : isDestinationView ? (
            // Single table view for selected airline's destinations (when both airline and destination selected)
            <div className="max-h-screen overflow-hidden">
              <AirlineTable
                data={filteredAirlines}
                isTop={true}
                isAirlineView={true}
                airlineName={effectiveAirline}
                limit={topLimit}
              />
            </div>
          ) : (
            // Two table view for top/bottom airlines (when no specific airline selected)
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 max-h-screen overflow-hidden">
              <div className="flex-shrink-0">
                <AirlineTable
                  data={filteredAirlines}
                  isTop={true}
                  limit={topLimit}
                />
              </div>
              <div className="flex-shrink-0">
                <AirlineTable
                  data={filteredAirlines}
                  isTop={false}
                  limit={topLimit}
                />
              </div>
            </div>
          )
        )}

        {/* Credits */}
        <div className="mt-10 text-center text-xs text-muted-foreground">
          <div className="flex flex-col items-center gap-1" dir="ltr">
            <span className="inline-flex items-center gap-1">
              <Github className="h-3.5 w-3.5" aria-hidden="true" />
              <span>GitHub:</span>{' '}
              <a
                href="https://github.com/Daniel1Maymon/israel-flights-etl"
                className="underline underline-offset-2 hover:text-foreground"
                target="_blank"
                rel="noreferrer"
              >
                israel-flights-etl
              </a>
            </span>
            <span className="inline-flex items-center gap-1">
              <Linkedin className="h-3.5 w-3.5" aria-hidden="true" />
              <span>LinkedIn:</span>{' '}
              <a
                href="https://www.linkedin.com/in/daniel-maymon/"
                className="underline underline-offset-2 hover:text-foreground"
                target="_blank"
                rel="noreferrer"
              >
                daniel-maymon
              </a>
            </span>
            <span>Data source: data.gov.il</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Index;
