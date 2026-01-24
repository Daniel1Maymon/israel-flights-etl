import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { useLanguage } from "@/contexts/LanguageContext";
import { useApiData } from "@/hooks/useApiData";
import { Calendar, MapPin, Clock, Plane } from "lucide-react";
import { getAllDestinations } from "@/lib/mockData";
import { API_ENDPOINTS } from "@/config/api";

interface DashboardFiltersProps {
  selectedDestination: string;
  onDestinationChange: (destination: string) => void;
  selectedDateRange: string;
  onDateRangeChange: (dateRange: string) => void;
  selectedDayOfWeek: string;
  onDayOfWeekChange: (dayOfWeek: string) => void;
  selectedAirline: string;
  onAirlineChange: (airline: string) => void;
}

export const DashboardFilters = ({ 
  selectedDestination, 
  onDestinationChange,
  selectedDateRange,
  onDateRangeChange,
  selectedDayOfWeek,
  onDayOfWeekChange,
  selectedAirline,
  onAirlineChange
}: DashboardFiltersProps) => {
  const { t, isRTL } = useLanguage();
  
  // Fetch real destinations from API
  const { data: destinationsData, loading: destinationsLoading, error: destinationsError } = useApiData(API_ENDPOINTS.DESTINATIONS);
  
  // Fetch real airlines from API
  const { data: airlinesData, loading: airlinesLoading, error: airlinesError } = useApiData(API_ENDPOINTS.AIRLINES);
  
  // Use real destinations if available, fallback to mock data
  const destinations = destinationsData && destinationsData.length > 0 
    ? destinationsData.map((dest: any) => dest.destination || dest)
    : getAllDestinations();
  
  // Use real airlines if available, fallback to empty array, sorted alphabetically
  const airlines = airlinesData && airlinesData.length > 0 
    ? airlinesData
        .map((airline: any) => airline.airline_name || airline.name)
        .filter((name: string) => name && name.trim() !== '') // Filter out empty names
        .sort((a: string, b: string) => a.toLowerCase().localeCompare(b.toLowerCase())) // Sort alphabetically
    : [];

  return (
    <Card className="bg-gradient-to-r from-primary/5 to-info/5 border border-primary/20">
      <CardContent className="flex flex-col sm:flex-row gap-4 p-6">
        <div className="flex items-center gap-3 flex-1">
          <MapPin className="h-5 w-5 text-primary" />
          <div className="flex-1">
            <label className="text-sm font-medium text-foreground mb-1 block text-left">
              {t('filters.destination')}
            </label>
            <Select value={selectedDestination} onValueChange={onDestinationChange}>
              <SelectTrigger className="w-full bg-background border-border">
                <SelectValue placeholder={t('filters.selectDestination')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="All">{t('filters.allDestinations')}</SelectItem>
                {destinations.map((destination) => (
                  <SelectItem key={destination} value={destination}>
                    {destination}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        
        <div className="flex items-center gap-3 flex-1">
          <Calendar className="h-5 w-5 text-primary" />
          <div className="flex-1">
            <label className="text-sm font-medium text-foreground mb-1 block text-left">
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
        </div>
        
        <div className="flex items-center gap-3 flex-1">
          <Clock className="h-5 w-5 text-primary" />
          <div className="flex-1">
            <label className="text-sm font-medium text-foreground mb-1 block text-left">
              {t('filters.dayOfWeek')}
            </label>
            <Select value={selectedDayOfWeek} onValueChange={onDayOfWeekChange}>
              <SelectTrigger className="w-full bg-background border-border">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all-days">{t('filters.allDays')}</SelectItem>
                <SelectItem value="monday">{t('filters.monday')}</SelectItem>
                <SelectItem value="tuesday">{t('filters.tuesday')}</SelectItem>
                <SelectItem value="wednesday">{t('filters.wednesday')}</SelectItem>
                <SelectItem value="thursday">{t('filters.thursday')}</SelectItem>
                <SelectItem value="friday">{t('filters.friday')}</SelectItem>
                <SelectItem value="saturday">{t('filters.saturday')}</SelectItem>
                <SelectItem value="sunday">{t('filters.sunday')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
        
        <div className="flex items-center gap-3 flex-1">
          <Plane className="h-5 w-5 text-primary" />
          <div className="flex-1">
            <label className="text-sm font-medium text-foreground mb-1 block text-left">
              {t('filters.airline')}
            </label>
            <Select value={selectedAirline} onValueChange={onAirlineChange}>
              <SelectTrigger className="w-full bg-background border-border">
                <SelectValue placeholder={t('filters.selectAirline')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="All">{t('filters.allAirlines')}</SelectItem>
                {airlines.map((airline) => (
                  <SelectItem key={airline} value={airline}>
                    {airline}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};