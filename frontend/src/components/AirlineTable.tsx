import { AirlineKPI } from "@/lib/mockData";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useLanguage } from "@/contexts/LanguageContext";
import { TrendingUp, TrendingDown } from "lucide-react";

interface AirlineTableProps {
  data: AirlineKPI[];
  isTop: boolean;
}

export const AirlineTable = ({ data, isTop }: AirlineTableProps) => {
  const { t, isRTL } = useLanguage();
  
  const title = isTop ? t('airline.top5') : t('airline.bottom5');
  
  // Debug: Log the RTL value
  console.log('AirlineTable isRTL:', isRTL, 'language:', t('language.hebrew'));
  
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
      <CardHeader className={`flex flex-row items-center space-y-0 pb-3 ${isRTL ? 'justify-end' : ''}`}>
        <div 
          className="flex items-center gap-2"
          style={isRTL ? { flexDirection: 'row-reverse' } : {}}
        >
          {isTop ? (
            <TrendingUp className="h-5 w-5 text-success" />
          ) : (
            <TrendingDown className="h-5 w-5 text-destructive" />
          )}
          <CardTitle className="text-xl font-semibold text-foreground">
            {title}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <Table className="airline-table">
          <TableHeader>
            <TableRow className="border-border/50">
              <TableHead className="font-semibold text-muted-foreground text-left">{t('airline.name')}</TableHead>
              <TableHead className="font-semibold text-muted-foreground text-center">{t('airline.onTime')} %</TableHead>
              <TableHead className="font-semibold text-muted-foreground text-center">{t('airline.avgDelay')}</TableHead>
              <TableHead className="font-semibold text-muted-foreground text-center">{t('airline.cancellations')} %</TableHead>
              <TableHead className="font-semibold text-muted-foreground text-center">{t('airline.flights')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((airline, index) => (
              <TableRow 
                key={airline.airline} 
                className="border-border/30 hover:bg-muted/30 transition-colors"
              >
                <TableCell className="font-medium text-foreground">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">#{index + 1}</span>
                    {airline.airline}
                  </div>
                </TableCell>
                <TableCell className="text-center">
                  <Badge className={getOnTimeColor(airline.onTimePercentage)}>
                    {airline.onTimePercentage.toFixed(1)}%
                  </Badge>
                </TableCell>
                <TableCell className="text-center text-foreground">
                  {airline.avgDelayMinutes.toFixed(1)} {t('airline.minutes')}
                </TableCell>
                <TableCell className="text-center">
                  <Badge className={getCancellationColor(airline.cancellationPercentage)}>
                    {airline.cancellationPercentage.toFixed(1)}%
                  </Badge>
                </TableCell>
                <TableCell className="text-center text-foreground font-medium">
                  {airline.flightCount.toLocaleString()}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
};