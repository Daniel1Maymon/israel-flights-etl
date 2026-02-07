import { useState, useMemo } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/LanguageContext";
import { BarChart3, Calendar, MapPin, Plane, RotateCcw } from "lucide-react";
import { UnifiedSearch } from "@/components/UnifiedSearch";
import { useApiData } from "@/hooks/useApiData";
import { API_ENDPOINTS } from "@/config/api";

type SearchType = "airline" | "airport" | "country" | "city";

interface DashboardFiltersProps {
  selectedAirport: string;
  onAirportChange: (airport: string) => void;
  selectedAirline: string;
  onAirlineChange: (airline: string) => void;
  selectedSearch: string;
  onSearchChange: (search: string, type: SearchType) => void;
  selectedDateRange: string;
  onDateRangeChange: (dateRange: string) => void;
  topLimit: number;
  onTopLimitChange: (limit: number) => void;
  onReset: () => void;
  resetSignal?: number;
}

export const DashboardFilters = ({ 
  selectedAirport,
  onAirportChange,
  selectedAirline,
  onAirlineChange,
  selectedSearch,
  onSearchChange,
  selectedDateRange,
  onDateRangeChange,
  topLimit,
  onTopLimitChange,
  onReset,
  resetSignal
}: DashboardFiltersProps) => {
  const { t, isRTL } = useLanguage();

  // Fetch airports and airlines for dropdowns
  const { data: destinationsData } = useApiData(API_ENDPOINTS.DESTINATIONS);
  const { data: airlinesData } = useApiData(API_ENDPOINTS.AIRLINES);

  // Process airports
  const allAirports = useMemo(() => {
    if (!destinationsData || destinationsData.length === 0) return [];
    const destinations: unknown[] = Array.isArray(destinationsData)
      ? destinationsData
      : (Array.isArray((destinationsData as Record<string, unknown>)?.destinations)
          ? ((destinationsData as Record<string, unknown>).destinations as unknown[])
          : []);
    return destinations
      .map((dest: unknown) => (dest as Record<string, unknown>).destination || dest)
      .filter((dest: unknown): dest is string => typeof dest === 'string' && dest.trim() !== '')
      .sort((a: string, b: string) => a.toLowerCase().localeCompare(b.toLowerCase()));
  }, [destinationsData]);

  // Process airlines
  const allAirlines = useMemo(() => {
    if (!airlinesData || airlinesData.length === 0) return [];
    return airlinesData
      .map((airline: unknown) => {
        const airlineObj = airline as Record<string, unknown>;
        return {
          code: (airlineObj.airline_code || airlineObj.code || '') as string,
          name: (airlineObj.airline_name || airlineObj.name || '') as string
        };
      })
      .filter((airline: { code: string; name: string }) => airline.name && airline.name.trim() !== '')
      .filter((airline: { code: string; name: string }, index: number, self: { code: string; name: string }[]) =>
        index === self.findIndex((a: { code: string; name: string }) => a.name.toLowerCase() === airline.name.toLowerCase())
      )
      .sort((a: { code: string; name: string }, b: { code: string; name: string }) =>
        a.name.toLowerCase().localeCompare(b.name.toLowerCase())
      )
      .map((a: { code: string; name: string }) => a.name);
  }, [airlinesData]);

  const topLimitOptions = [5, 10, 15, 20];

  return (
    <Card className="bg-gradient-to-r from-primary/5 to-info/5 border border-primary/20">
      <CardContent className="flex flex-col sm:flex-row gap-4 p-6">
        {/* Airport Dropdown */}
        <div className="flex-1">
          <label className="text-sm font-medium text-foreground mb-1 block text-left flex items-center gap-2">
            <MapPin className="h-4 w-4 text-primary" />
            {t('filters.airport') || "Airport"}
          </label>
          <Select value={selectedAirport} onValueChange={onAirportChange}>
            <SelectTrigger className="w-full bg-background border-border">
              <SelectValue placeholder={t('filters.all') || "All"} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="All">{t('filters.all') || "All"}</SelectItem>
              {allAirports.map((airport: string) => (
                <SelectItem key={airport} value={airport}>
                  {airport}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Airline Dropdown */}
        <div className="flex-1">
          <label className="text-sm font-medium text-foreground mb-1 block text-left flex items-center gap-2">
            <Plane className="h-4 w-4 text-primary" />
            {t('filters.airline') || "Airline"}
          </label>
          <Select value={selectedAirline} onValueChange={onAirlineChange}>
            <SelectTrigger className="w-full bg-background border-border">
              <SelectValue placeholder={t('filters.all') || "All"} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="All">{t('filters.all') || "All"}</SelectItem>
              {allAirlines.map((airline: string) => (
                <SelectItem key={airline} value={airline}>
                  {airline}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Search Bar with Airport/Country/City/Airline options */}
        <UnifiedSearch
          selectedValue={selectedSearch}
          onValueChange={onSearchChange}
          label={t('common.search') || "Search"}
          allowedTypes={["airport", "country", "city", "airline"]}
          defaultType="airport"
          resetSignal={resetSignal}
        />
        
        {/* Date Range */}
        <div className="flex-1">
          <label className="text-sm font-medium text-foreground mb-1 block text-left flex items-center gap-2">
            <Calendar className="h-4 w-4 text-primary" />
            {t('filters.dateRange')}
          </label>
          <Select value={selectedDateRange} onValueChange={onDateRangeChange}>
            <SelectTrigger className="w-full bg-background border-border">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all-time">{t('filters.allTime')}</SelectItem>
              <SelectItem value="last-7-days">{t('filters.last7Days')}</SelectItem>
              <SelectItem value="last-30-days">{t('filters.last30Days')}</SelectItem>
              <SelectItem value="last-90-days">{t('filters.last90Days')}</SelectItem>
              <SelectItem value="last-year">{t('filters.lastYear')}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Top/Bottom Count */}
        <div className="flex-1">
          <label className="text-sm font-medium text-foreground mb-1 block text-left flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-primary" />
            {t('filters.topCount')}
          </label>
          <Select value={String(topLimit)} onValueChange={(value) => onTopLimitChange(Number(value))}>
            <SelectTrigger className="w-full bg-background border-border">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {topLimitOptions.map((option) => (
                <SelectItem key={option} value={String(option)}>
                  {option}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="flex items-end">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="h-10 text-xs px-3"
            onClick={onReset}
          >
            <RotateCcw className="h-3 w-3 mr-1.5" />
            {t('common.clear') || "Clear"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};
