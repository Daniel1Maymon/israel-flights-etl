import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useLanguage } from "@/contexts/LanguageContext";
import { Plane, TrendingUp, Clock, XCircle, CheckCircle } from "lucide-react";

interface AirlinePerformanceCardProps {
  airline: {
    airline_name: string;
    airline_code: string;
    on_time_percentage: number;
    avg_delay_minutes: number;
    avg_delay_all_flights: number;
    cancellation_percentage: number;
    total_flights: number;
    on_time_flights: number;
    delayed_flights: number;
    cancelled_flights: number;
    destinations?: string[];
    data_quality_score?: number;
  };
}

export const AirlinePerformanceCard = ({ airline }: AirlinePerformanceCardProps) => {
  const { t, isRTL } = useLanguage();
  
  const getOnTimeColor = (percentage: number) => {
    if (percentage >= 85) return "bg-success text-white";
    if (percentage >= 75) return "bg-warning text-background";
    return "bg-destructive text-white";
  };

  const getCancellationColor = (percentage: number) => {
    if (percentage <= 2) return "bg-success text-white";
    if (percentage <= 4) return "bg-warning text-background";
    return "bg-destructive text-white";
  };

  return (
    <Card className="bg-gradient-to-br from-card to-secondary/50 border border-border/50 shadow-[var(--shadow-card)]">
      <CardHeader className="flex flex-row items-center space-y-0 pb-3">
        <div className="flex items-center gap-2">
          <Plane className="h-5 w-5 text-primary" />
          <CardTitle className="text-xl font-semibold text-foreground">
            {airline.airline_name} ({airline.airline_code})
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Key Metrics Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <div className="bg-muted/50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-primary">
              {airline.total_flights.toLocaleString()}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {t('airline.flights') || "Total Flights"}
            </div>
          </div>
          
          <div className="bg-muted/50 rounded-lg p-3 text-center">
            <Badge className={`${getOnTimeColor(airline.on_time_percentage)} text-sm px-2 py-1 w-full justify-center`}>
              {airline.on_time_percentage.toFixed(1)}%
            </Badge>
            <div className="text-xs text-muted-foreground mt-1">
              {t('airline.onTime') || "On Time"}
            </div>
          </div>
          
          <div className="bg-muted/50 rounded-lg p-3 text-center">
            <div className="text-2xl font-bold text-foreground">
              {airline.avg_delay_all_flights.toFixed(1)}
            </div>
            <div className="text-xs text-muted-foreground mt-1">
              {t('airline.avgDelay') || "Avg Delay"} ({t('airline.minutes') || "min"})
            </div>
          </div>
          
          <div className="bg-muted/50 rounded-lg p-3 text-center">
            <Badge className={`${getCancellationColor(airline.cancellation_percentage)} text-sm px-2 py-1 w-full justify-center`}>
              {airline.cancellation_percentage.toFixed(1)}%
            </Badge>
            <div className="text-xs text-muted-foreground mt-1">
              {t('airline.cancellations') || "Cancellations"}
            </div>
          </div>
        </div>

        {/* Detailed Breakdown */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-2 border-t border-border/50">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-4 w-4 text-success" />
            <div>
              <div className="text-sm font-medium">{airline.on_time_flights.toLocaleString()}</div>
              <div className="text-xs text-muted-foreground">{t('airline.onTime') || "On Time Flights"}</div>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <Clock className="h-4 w-4 text-warning" />
            <div>
              <div className="text-sm font-medium">{airline.delayed_flights.toLocaleString()}</div>
              <div className="text-xs text-muted-foreground">{t('airline.delays') || "Delayed Flights"}</div>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <XCircle className="h-4 w-4 text-destructive" />
            <div>
              <div className="text-sm font-medium">{airline.cancelled_flights.toLocaleString()}</div>
              <div className="text-xs text-muted-foreground">{t('airline.cancellations') || "Cancelled Flights"}</div>
            </div>
          </div>
        </div>

        {/* Destinations (if available) */}
        {airline.destinations && airline.destinations.length > 0 && (
          <div className="pt-2 border-t border-border/50">
            <div className="text-sm font-medium mb-2">
              {t('airline.destinations') || "Destinations"} ({airline.destinations.length})
            </div>
            <div className="flex flex-wrap gap-2">
              {airline.destinations.slice(0, 10).map((dest, index) => (
                <Badge key={index} variant="outline" className="text-xs">
                  {dest}
                </Badge>
              ))}
              {airline.destinations.length > 10 && (
                <Badge variant="outline" className="text-xs">
                  +{airline.destinations.length - 10} more
                </Badge>
              )}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
