import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useLanguage } from "@/contexts/LanguageContext";
import { Database, Loader2, AlertCircle, ChevronLeft, ChevronRight, ArrowUpDown, ArrowUp, ArrowDown } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
interface Flight {
  flight_id: string;
  airline_code: string;
  flight_number: string;
  direction: string;
  location_iata: string;
  scheduled_time: string;
  actual_time: string | null;
  airline_name: string;
  location_en: string;
  location_he: string;
  location_city_en: string;
  country_en: string;
  country_he: string;
  terminal: string | null;
  checkin_counters: string | null;
  checkin_zone: string | null;
  status_en: string;
  status_he: string;
  delay_minutes: number;
  scrape_timestamp: string | null;
  raw_s3_path: string;
}

interface PaginationInfo {
  page: number;
  size: number;
  total: number;
  pages: number;
  has_next: boolean;
  has_prev: boolean;
}

interface PaginatedFlightsTableProps {
  data: Flight[];
  pagination: PaginationInfo | null;
  loading: boolean;
  error: string | null;
  onPageChange: (page: number) => void;
  onPageSizeChange: (size: number) => void;
  onSort: (field: string) => void;
  currentPage: number;
  pageSize: number;
  sortField: string;
  sortDirection: 'asc' | 'desc';
}

export const PaginatedFlightsTable = ({ 
  data, 
  pagination, 
  loading, 
  error, 
  onPageChange, 
  onPageSizeChange, 
  onSort, 
  currentPage, 
  pageSize, 
  sortField, 
  sortDirection 
}: PaginatedFlightsTableProps) => {
  const { t, isRTL } = useLanguage();

  const getStatusColor = (status: string) => {
    if (status.includes('On Time') || status.includes('בזמן')) return "bg-green-500 text-white";
    if (status.includes('Boarding') || status.includes('עלייה')) return "bg-blue-500 text-white";
    if (status.includes('Landed') || status.includes('נחת')) return "bg-primary text-white";
    if (status.includes('Delayed') || status.includes('עיכוב')) return "bg-yellow-500 text-black";
    if (status.includes('Cancelled') || status.includes('בוטל')) return "bg-red-500 text-white";
    return "bg-gray-500 text-white";
  };

  const getDirectionIcon = (direction: string) => {
    return direction === 'D' ? '✈️' : '🛬';
  };

  const formatTime = (timeString: string | null) => {
    if (!timeString) return '-';
    return new Date(timeString).toLocaleTimeString('en-US', { 
      hour: '2-digit', 
      minute: '2-digit',
      timeZone: 'Asia/Jerusalem'
    });
  };

  const formatDate = (timeString: string | null) => {
    if (!timeString) return '-';
    return new Date(timeString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      timeZone: 'Asia/Jerusalem'
    });
  };

  const getSortIcon = (field: string) => {
    if (field !== sortField) return <ArrowUpDown className="h-4 w-4" />;
    return sortDirection === 'asc' ? <ArrowUp className="h-4 w-4" /> : <ArrowDown className="h-4 w-4" />;
  };

  const handleSort = (field: string) => {
    onSort(field);
  };

  if (loading) {
    return (
      <Card className="bg-gradient-to-br from-card to-secondary/50 border border-border/50 shadow-[var(--shadow-card)]">
        <CardHeader className={`flex flex-row items-center space-y-0 pb-3 ${isRTL ? 'justify-end' : ''}`}>
          <div className={`flex items-center gap-2 ${isRTL ? 'flex-row-reverse' : ''}`}>
            <Database className="h-5 w-5 text-primary" />
            <CardTitle className="text-xl font-semibold text-foreground">
              {t('flights.title')}
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <span className="ml-2 text-muted-foreground">{t('common.loading')}</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="bg-gradient-to-br from-card to-secondary/50 border border-border/50 shadow-[var(--shadow-card)]">
        <CardHeader className={`flex flex-row items-center space-y-0 pb-3 ${isRTL ? 'justify-end' : ''}`}>
          <div className={`flex items-center gap-2 ${isRTL ? 'flex-row-reverse' : ''}`}>
            <Database className="h-5 w-5 text-primary" />
            <CardTitle className="text-xl font-semibold text-foreground">
              {t('flights.title')}
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              {error}
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>
    );
  }

  if (!data || data.length === 0) {
    return (
      <Card className="bg-gradient-to-br from-card to-secondary/50 border border-border/50 shadow-[var(--shadow-card)]">
        <CardHeader className={`flex flex-row items-center space-y-0 pb-3 ${isRTL ? 'justify-end' : ''}`}>
          <div className={`flex items-center gap-2 ${isRTL ? 'flex-row-reverse' : ''}`}>
            <Database className="h-5 w-5 text-primary" />
            <CardTitle className="text-xl font-semibold text-foreground">
              {t('flights.title')}
            </CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="text-center py-8 text-muted-foreground">
            {t('database.noData')}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-gradient-to-br from-card to-secondary/50 border border-border/50 shadow-[var(--shadow-card)]">
      <CardHeader className={`flex flex-row items-center space-y-0 pb-3 ${isRTL ? 'justify-end' : ''}`}>
        <div className={`flex items-center gap-2 ${isRTL ? 'flex-row-reverse' : ''}`}>
          <Database className="h-5 w-5 text-primary" />
          <CardTitle className="text-xl font-semibold text-foreground">
            {t('flights.title')}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        {/* Pagination Controls - Top */}
        <div className="flex flex-col sm:flex-row justify-between items-center gap-4 mb-6">
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">
              Showing {((currentPage - 1) * pageSize) + 1} to {Math.min(currentPage * pageSize, pagination?.total || 0)} of {pagination?.total || 0} flights
            </span>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-sm text-muted-foreground">Per page:</span>
            <Select value={pageSize.toString()} onValueChange={(value) => onPageSizeChange(parseInt(value))}>
              <SelectTrigger className="w-20">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="10">10</SelectItem>
                <SelectItem value="25">25</SelectItem>
                <SelectItem value="50">50</SelectItem>
                <SelectItem value="100">100</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="border-border/50">
                <TableHead className="font-semibold text-muted-foreground text-center">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleSort('direction')}
                    className="h-auto p-0 font-semibold"
                  >
                    {t('flights.direction')} {getSortIcon('direction')}
                  </Button>
                </TableHead>
                <TableHead className="font-semibold text-muted-foreground text-left">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleSort('airline_name')}
                    className="h-auto p-0 font-semibold"
                  >
                    {t('flights.airline')} {getSortIcon('airline_name')}
                  </Button>
                </TableHead>
                <TableHead className="font-semibold text-muted-foreground text-center">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleSort('flight_number')}
                    className="h-auto p-0 font-semibold"
                  >
                    {t('flights.flight')} {getSortIcon('flight_number')}
                  </Button>
                </TableHead>
                <TableHead className="font-semibold text-muted-foreground text-left">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleSort('location_en')}
                    className="h-auto p-0 font-semibold"
                  >
                    {t('flights.destination')} {getSortIcon('location_en')}
                  </Button>
                </TableHead>
                <TableHead className="font-semibold text-muted-foreground text-center">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleSort('scheduled_time')}
                    className="h-auto p-0 font-semibold"
                  >
                    {t('flights.scheduled')} {getSortIcon('scheduled_time')}
                  </Button>
                </TableHead>
                <TableHead className="font-semibold text-muted-foreground text-center">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleSort('actual_time')}
                    className="h-auto p-0 font-semibold"
                  >
                    {t('flights.actual')} {getSortIcon('actual_time')}
                  </Button>
                </TableHead>
                <TableHead className="font-semibold text-muted-foreground text-center">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleSort('status_en')}
                    className="h-auto p-0 font-semibold"
                  >
                    {t('flights.status')} {getSortIcon('status_en')}
                  </Button>
                </TableHead>
                <TableHead className="font-semibold text-muted-foreground text-center">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleSort('delay_minutes')}
                    className="h-auto p-0 font-semibold"
                  >
                    {t('flights.delay')} {getSortIcon('delay_minutes')}
                  </Button>
                </TableHead>
                <TableHead className="font-semibold text-muted-foreground text-center">
                  {t('flights.terminal')}
                </TableHead>
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
                      <span className="text-sm">
                        {isRTL ? flight.location_he : flight.location_en}
                      </span>
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {isRTL ? flight.country_he : flight.country_en}
                    </div>
                  </TableCell>
                  <TableCell className="text-center font-mono text-sm">
                    <div>{formatTime(flight.scheduled_time)}</div>
                    <div className="text-xs text-muted-foreground">{formatDate(flight.scheduled_time)}</div>
                  </TableCell>
                  <TableCell className="text-center font-mono text-sm">
                    <div>{formatTime(flight.actual_time)}</div>
                    <div className="text-xs text-muted-foreground">{formatDate(flight.actual_time)}</div>
                  </TableCell>
                  <TableCell className="text-center">
                    <Badge className={getStatusColor(flight.status_en)}>
                      {isRTL ? flight.status_he : flight.status_en}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-center">
                    {flight.delay_minutes > 0 ? (
                      <span className="text-red-500 font-medium">
                        +{flight.delay_minutes} {t('flights.minutes')}
                      </span>
                    ) : (
                      <span className="text-green-500 font-medium">
                        {t('flights.onTime')}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="text-center font-mono text-sm">
                    {flight.terminal || '-'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>

        {/* Pagination Controls - Bottom */}
        {pagination && (
          <div className="flex flex-col sm:flex-row justify-between items-center gap-4 mt-6">
            <div className="text-sm text-muted-foreground">
              Page {currentPage} of {pagination.pages}
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => onPageChange(currentPage - 1)}
                disabled={!pagination.has_prev}
              >
                <ChevronLeft className="h-4 w-4" />
                Previous
              </Button>
              
              {/* Page numbers */}
              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(5, pagination.pages) }, (_, i) => {
                  const startPage = Math.max(1, currentPage - 2);
                  const pageNum = startPage + i;
                  if (pageNum > pagination.pages) return null;
                  
                  return (
                    <Button
                      key={pageNum}
                      variant={pageNum === currentPage ? "default" : "outline"}
                      size="sm"
                      onClick={() => onPageChange(pageNum)}
                      className="w-10"
                    >
                      {pageNum}
                    </Button>
                  );
                })}
              </div>
              
              <Button
                variant="outline"
                size="sm"
                onClick={() => onPageChange(currentPage + 1)}
                disabled={!pagination.has_next}
              >
                Next
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
