import { Flight } from "@/lib/mockFlightData";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useLanguage } from "@/contexts/LanguageContext";
import { Plane, Clock, MapPin } from "lucide-react";

interface FlightsTableProps {
  data: Flight[];
}

export const FlightsTable = ({ data }: FlightsTableProps) => {
  const { t, isRTL } = useLanguage();

  const getStatusColor = (status: string) => {
    if (status.includes('On Time') || status.includes('בזמן')) return "bg-success text-white";
    if (status.includes('Boarding') || status.includes('עלייה')) return "bg-info text-white";
    if (status.includes('Landed') || status.includes('נחת')) return "bg-primary text-white";
    return "bg-warning text-background";
  };

  const getDirectionIcon = (direction: string) => {
    return direction === 'D' ? '✈️' : '🛬';
  };

  const formatTime = (timeString: string) => {
    return new Date(timeString).toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      timeZone: 'Asia/Jerusalem'
    });
  };

  return (
    <Card className="bg-gradient-to-br from-card to-secondary/50 border border-border/50 shadow-[var(--shadow-card)]">
      <CardHeader className={`flex flex-row items-center space-y-0 pb-3 ${isRTL ? 'justify-end' : ''}`}>
        <div className={`flex items-center gap-2 ${isRTL ? 'flex-row-reverse' : ''}`}>
          <Plane className="h-5 w-5 text-primary" />
          <CardTitle className="text-xl font-semibold text-foreground">
            {t('flights.title')}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow className="border-border/50">
              <TableHead className="font-semibold text-muted-foreground text-center">{t('flights.direction')}</TableHead>
              <TableHead className="font-semibold text-muted-foreground text-left">{t('flights.airline')}</TableHead>
              <TableHead className="font-semibold text-muted-foreground text-center">{t('flights.flight')}</TableHead>
              <TableHead className="font-semibold text-muted-foreground text-left">{t('flights.destination')}</TableHead>
              <TableHead className="font-semibold text-muted-foreground text-center">{t('flights.scheduled')}</TableHead>
              <TableHead className="font-semibold text-muted-foreground text-center">{t('flights.actual')}</TableHead>
              <TableHead className="font-semibold text-muted-foreground text-center">{t('flights.status')}</TableHead>
              <TableHead className="font-semibold text-muted-foreground text-center">{t('flights.delay')}</TableHead>
              <TableHead className="font-semibold text-muted-foreground text-center">{t('flights.terminal')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((flight) => (
              <TableRow 
                key={flight.flight_id} 
                className="border-border/30 hover:bg-muted/30 transition-colors"
              >
                <TableCell className="text-center text-2xl">
                  {getDirectionIcon(flight.direction)}
                </TableCell>
                <TableCell className="font-medium text-foreground">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">{flight.airline_code}</span>
                    {isRTL ? flight.airline_name : flight.airline_name}
                  </div>
                </TableCell>
                <TableCell className="text-center font-mono text-sm">
                  {flight.flight_number}
                </TableCell>
                <TableCell className="text-foreground">
                  <div className="flex items-center gap-1">
                    <MapPin className="h-3 w-3 text-muted-foreground" />
                    <span className="text-sm">
                      {isRTL ? flight.location_he : flight.location_en}
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {isRTL ? flight.country_he : flight.country_en}
                  </div>
                </TableCell>
                <TableCell className="text-center font-mono text-sm">
                  {formatTime(flight.scheduled_time)}
                </TableCell>
                <TableCell className="text-center font-mono text-sm">
                  {formatTime(flight.actual_time)}
                </TableCell>
                <TableCell className="text-center">
                  <Badge className={getStatusColor(flight.status_en)}>
                    {isRTL ? flight.status_he : flight.status_en}
                  </Badge>
                </TableCell>
                <TableCell className="text-center">
                  {flight.delay_minutes > 0 ? (
                    <span className="text-destructive font-medium">
                      +{flight.delay_minutes} {t('flights.minutes')}
                    </span>
                  ) : (
                    <span className="text-success font-medium">
                      {t('flights.onTime')}
                    </span>
                  )}
                </TableCell>
                <TableCell className="text-center font-mono text-sm">
                  {flight.terminal}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
};
