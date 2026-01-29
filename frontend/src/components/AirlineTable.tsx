import { AirlineKPI } from "@/lib/mockData.ts";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useLanguage } from "@/contexts/LanguageContext";
import { TrendingUp, TrendingDown, ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { useState } from "react";

interface AirlineTableProps {
  data: AirlineKPI[];
  isTop: boolean;
  isAirlineView?: boolean;
  airlineName?: string;
  limit?: number;
}

type SortField = 'airline' | 'onTimePercentage' | 'avgDelayMinutes' | 'cancellationPercentage' | 'flightCount';
type SortDirection = 'asc' | 'desc';

export const AirlineTable = ({ data, isTop, isAirlineView = false, airlineName, limit = 5 }: AirlineTableProps) => {
  const { t, isRTL } = useLanguage();
  const displayLimit = Math.max(1, limit);
  const getTitleWithLimit = (key: string) => t(key).replace('{count}', String(displayLimit));
  
  const title = isAirlineView 
    ? `${t('airline.destinationsFor')} ${airlineName}`
    : (isTop ? getTitleWithLimit('airline.topN') : getTitleWithLimit('airline.bottomN'));
  
  // Sorting state
  const [sortField, setSortField] = useState<SortField>('onTimePercentage');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  
  // Debug: Log the RTL value
  
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

  // Sorting functions
  const handleSort = (field: SortField) => {
    if (sortField === field) {
      // For airline/destination fields, always use ascending order (no toggle)
      if (field === 'airline') {
        setSortDirection('asc');
      } else {
        // Other fields can toggle between asc and desc
        setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
      }
    } else {
      setSortField(field);
      // Default to ascending for airline field, ascending for others too
      setSortDirection('asc');
    }
  };

  const getSortIcon = (field: SortField) => {
    if (field !== sortField) return <ArrowUpDown className="h-4 w-4" />;
    return sortDirection === 'asc' ? <ArrowUp className="h-4 w-4" /> : <ArrowDown className="h-4 w-4" />;
  };

  const getSortButtonClass = (field: SortField) => {
    const base = "h-auto p-0 font-semibold text-xs flex flex-wrap items-center justify-center gap-1 whitespace-normal leading-tight text-center";
    if (field !== sortField) return base;
    return `${base} border-2 border-foreground/80 rounded-sm px-1 py-0.5`;
  };

  // Sort data based on current sort field and direction
  const sortedData = [...data].sort((a, b) => {
    let aValue: any;
    let bValue: any;
    
    switch (sortField) {
      case 'airline':
        aValue = a.airline.toLowerCase();
        bValue = b.airline.toLowerCase();
        break;
      case 'onTimePercentage':
        aValue = a.onTimePercentage;
        bValue = b.onTimePercentage;
        break;
      case 'avgDelayMinutes':
        aValue = a.avgDelayMinutes;
        bValue = b.avgDelayMinutes;
        break;
      case 'cancellationPercentage':
        aValue = a.cancellationPercentage;
        bValue = b.cancellationPercentage;
        break;
      case 'flightCount':
        aValue = a.flightCount;
        bValue = b.flightCount;
        break;
      default:
        return 0;
    }
    
    if (sortDirection === 'asc') {
      if (typeof aValue === 'string') {
        return aValue.localeCompare(bValue);
      }
      return aValue - bValue;
    } else {
      if (typeof aValue === 'string') {
        return bValue.localeCompare(aValue);
      }
      return bValue - aValue;
    }
  });

  // Show top or bottom based on the isTop prop and limit
  const displayData = isTop ? sortedData.slice(0, displayLimit) : sortedData.slice(-displayLimit);


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
      <CardContent className="p-0">
        <div className="max-h-96 overflow-y-auto">
          <Table className="airline-table w-full table-fixed">
          <TableHeader>
            <TableRow className="border-border/50">
              <TableHead className="font-semibold text-muted-foreground text-left w-[28%] whitespace-normal break-words">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('airline')}
                  className={getSortButtonClass('airline')}
                >
                  {isAirlineView ? t('airline.destination') : t('airline.name')} {getSortIcon('airline')}
                </Button>
              </TableHead>
              <TableHead className="font-semibold text-muted-foreground text-center w-[18%] whitespace-normal break-words">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('onTimePercentage')}
                  className={getSortButtonClass('onTimePercentage')}
                >
                  {t('airline.onTime')} % {getSortIcon('onTimePercentage')}
                </Button>
              </TableHead>
              <TableHead className="font-semibold text-muted-foreground text-center w-[18%] whitespace-normal break-words">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('avgDelayMinutes')}
                  className={getSortButtonClass('avgDelayMinutes')}
                >
                  {t('airline.avgDelay')} {getSortIcon('avgDelayMinutes')}
                </Button>
              </TableHead>
              <TableHead className="font-semibold text-muted-foreground text-center w-[18%] whitespace-normal break-words">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('cancellationPercentage')}
                  className={getSortButtonClass('cancellationPercentage')}
                >
                  {t('airline.cancellations')} % {getSortIcon('cancellationPercentage')}
                </Button>
              </TableHead>
              <TableHead className="font-semibold text-muted-foreground text-center w-[18%] whitespace-normal break-words">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => handleSort('flightCount')}
                  className={getSortButtonClass('flightCount')}
                >
                  {t('airline.flights')} {getSortIcon('flightCount')}
                </Button>
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {displayData.map((airline, index) => (
              <TableRow 
                key={`${airline.airline}-${index}`} 
                className="border-border/30 hover:bg-muted/30 transition-colors"
              >
                <TableCell className="font-medium text-foreground px-1 py-1">
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-muted-foreground">{index + 1}</span>
                    <span className="text-xs truncate">{airline.airline}</span>
                  </div>
                </TableCell>
                <TableCell className="text-center px-1 py-1">
                  <Badge className={`${getOnTimeColor(airline.onTimePercentage || 0)} text-xs px-1 py-0`}>
                    {(airline.onTimePercentage || 0).toFixed(1)}%
                  </Badge>
                </TableCell>
                <TableCell className="text-center text-foreground px-1 py-1 text-xs">
                  {(airline.avgDelayMinutes || 0).toFixed(1)} {t('airline.minutes')}
                </TableCell>
                <TableCell className="text-center px-1 py-1">
                  <Badge className={`${getCancellationColor(airline.cancellationPercentage || 0)} text-xs px-1 py-0`}>
                    {(airline.cancellationPercentage || 0).toFixed(1)}%
                  </Badge>
                </TableCell>
                <TableCell className="text-center text-foreground font-medium px-1 py-1 text-xs">
                  {(airline.flightCount || 0).toLocaleString()}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        </div>
      </CardContent>
    </Card>
  );
};
