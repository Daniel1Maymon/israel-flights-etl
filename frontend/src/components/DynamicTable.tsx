import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useLanguage } from "@/contexts/LanguageContext";
import { Database, Loader2, AlertCircle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface DynamicTableProps {
  data: Record<string, unknown>[];
  loading: boolean;
  error: string | null;
  title: string;
}

export const DynamicTable = ({ data, loading, error, title }: DynamicTableProps) => {
  const { t, isRTL } = useLanguage();

  // Get column headers from the first row of data
  const getColumns = () => {
    if (!data || data.length === 0) return [];
    return Object.keys(data[0]);
  };

  // Format cell value for display
  const formatCellValue = (value: unknown, column: string): string => {
    if (value === null || value === undefined) return '-';
    
    // Handle timestamps
    if (column.includes('time') || column.includes('timestamp')) {
      try {
        return new Date(value as string | number | Date).toLocaleString();
      } catch {
        return value.toString();
      }
    }
    
    // Handle boolean values
    if (typeof value === 'boolean') {
      return value ? 'Yes' : 'No';
    }
    
    // Handle arrays
    if (Array.isArray(value)) {
      return value.join(', ');
    }
    
    // Handle objects
    if (typeof value === 'object') {
      return JSON.stringify(value);
    }
    
    return value.toString();
  };

  // Get status color for status-like columns
  const getStatusColor = (value: string, column: string) => {
    if (!column.toLowerCase().includes('status')) return '';
    
    const status = value.toLowerCase();
    if (status.includes('on time') || status.includes('בזמן') || status.includes('success')) {
      return "bg-success text-white";
    }
    if (status.includes('boarding') || status.includes('עלייה') || status.includes('info')) {
      return "bg-info text-white";
    }
    if (status.includes('landed') || status.includes('נחת') || status.includes('completed')) {
      return "bg-primary text-white";
    }
    if (status.includes('delayed') || status.includes('עיכוב') || status.includes('warning')) {
      return "bg-warning text-background";
    }
    if (status.includes('cancelled') || status.includes('בוטל') || status.includes('error')) {
      return "bg-destructive text-white";
    }
    return "bg-secondary text-secondary-foreground";
  };

  // Check if a column should be displayed as a badge
  const shouldShowAsBadge = (column: string, value: unknown) => {
    const statusColumns = ['status', 'status_en', 'status_he', 'direction'];
    return statusColumns.some(statusCol => column.toLowerCase().includes(statusCol)) || 
           (typeof value === 'string' && value.length < 20);
  };

  // Get direction icon for direction columns
  const getDirectionIcon = (value: string, column: string) => {
    if (!column.toLowerCase().includes('direction')) return null;
    return value === 'D' ? '✈️' : '🛬';
  };

  const columns = getColumns();

  if (loading) {
    return (
      <Card className="bg-gradient-to-br from-card to-secondary/50 border border-border/50 shadow-[var(--shadow-card)]">
        <CardHeader className={`flex flex-row items-center space-y-0 pb-3 ${isRTL ? 'justify-end' : ''}`}>
          <div className={`flex items-center gap-2 ${isRTL ? 'flex-row-reverse' : ''}`}>
            <Database className="h-5 w-5 text-primary" />
            <CardTitle className="text-xl font-semibold text-foreground">
              {title}
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
              {title}
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
              {title}
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
            {title}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="border-border/50">
                {columns.map((column) => (
                  <TableHead 
                    key={column} 
                    className="font-semibold text-muted-foreground text-left whitespace-nowrap"
                  >
                    {column.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((row, rowIndex) => (
                <TableRow 
                  key={rowIndex} 
                  className="border-border/30 hover:bg-muted/30 transition-colors"
                >
                  {columns.map((column) => {
                    const value = row[column];
                    const formattedValue = formatCellValue(value, column);
                    const directionIcon = typeof value === 'string' ? getDirectionIcon(value, column) : null;
                    const statusColor = getStatusColor(formattedValue, column);
                    const showAsBadge = shouldShowAsBadge(column, value);

                    return (
                      <TableCell key={column} className="text-foreground">
                        <div className="flex items-center gap-2">
                          {directionIcon && (
                            <span className="text-lg">{directionIcon}</span>
                          )}
                          {showAsBadge ? (
                            <Badge className={statusColor || "bg-secondary text-secondary-foreground"}>
                              {formattedValue}
                            </Badge>
                          ) : (
                            <span className="text-sm">{formattedValue}</span>
                          )}
                        </div>
                      </TableCell>
                    );
                  })}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
};
