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
  const [isDatabaseMode, setIsDatabaseMode] = useState(false);
  const { t, isRTL } = useLanguage();
  
  // API endpoint - you can change this to your actual backend URL
  const API_ENDPOINT = isDatabaseMode ? 'http://localhost:8000/api/v1/flights/' : '';
  
  // Fetch data from API when in database mode
  const { data: apiData, loading, error } = useApiData(API_ENDPOINT);
  
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
  } = usePaginatedFlights(API_ENDPOINT);
  
  const filteredData = filterAirlinesByDestination(selectedDestination);
  const topAirlines = getTopAirlines(filteredData, 5);
  const bottomAirlines = getBottomAirlines(filteredData, 5);

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
              {filteredData.length}
            </div>
            <div className="text-sm text-muted-foreground">{t('airline.total')}</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-success">
              {filteredData.reduce((sum, airline) => sum + airline.flightCount, 0).toLocaleString()}
            </div>
            <div className="text-sm text-muted-foreground">{t('airline.totalFlights')}</div>
          </div>
          <div className="bg-card border border-border rounded-lg p-4 text-center">
            <div className="text-2xl font-bold text-info">
              {(filteredData.reduce((sum, airline) => sum + airline.onTimePercentage, 0) / filteredData.length).toFixed(1)}%
            </div>
            <div className="text-sm text-muted-foreground">{t('airline.avgOnTime')}</div>
          </div>
        </div>

        {/* Filters */}
        <div className="mb-8">
          <DashboardFilters
            selectedDestination={selectedDestination}
            onDestinationChange={setSelectedDestination}
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