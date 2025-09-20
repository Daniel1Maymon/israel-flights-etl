import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { useLanguage } from "@/contexts/LanguageContext";
import { Calendar, MapPin } from "lucide-react";
import { getAllDestinations } from "@/lib/mockData";

interface DashboardFiltersProps {
  selectedDestination: string;
  onDestinationChange: (destination: string) => void;
}

export const DashboardFilters = ({ 
  selectedDestination, 
  onDestinationChange 
}: DashboardFiltersProps) => {
  const { t, isRTL } = useLanguage();
  const destinations = getAllDestinations();

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
            <Select defaultValue="last-30-days">
              <SelectTrigger className="w-full bg-background border-border">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="last-7-days">{t('filters.last7Days')}</SelectItem>
                <SelectItem value="last-30-days">{t('filters.last30Days')}</SelectItem>
                <SelectItem value="last-90-days">{t('filters.last90Days')}</SelectItem>
                <SelectItem value="last-year">{t('filters.lastYear')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};