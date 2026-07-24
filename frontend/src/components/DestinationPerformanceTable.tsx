import { useState } from "react";
import { useLanguage } from "@/contexts/LanguageContext";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ArrowUpDown, ArrowUp, ArrowDown, PlaneTakeoff } from "lucide-react";

export interface AirlinePerformanceRow {
  airline_name: string;
  total_flights: number;
  on_time_pct: number;
  cancelled_pct: number;
  avg_delay_minutes_positive_only: number | null;
}

type SortField = keyof AirlinePerformanceRow;
type SortDir = "asc" | "desc";

interface Props {
  city: string;
  cityHe?: string | null;
  data: AirlinePerformanceRow[];
  loading?: boolean;
  /** Overrides the "airline performance for {city}" heading (e.g. the default leaderboard). */
  title?: string;
  /** Initial column to sort by. Defaults to average delay (ascending). */
  initialSortField?: SortField;
  initialSortDir?: SortDir;
  /** If set, only the first N rows are shown AFTER sorting the full data set.
   *  Sorting therefore always ranks the whole data set, not just the visible rows. */
  displayLimit?: number;
}

export const DestinationPerformanceTable = ({
  city,
  cityHe,
  data,
  loading,
  title: titleOverride,
  initialSortField = "avg_delay_minutes_positive_only",
  initialSortDir = "asc",
  displayLimit,
}: Props) => {
  const { t, language } = useLanguage();

  const [sortField, setSortField] = useState<SortField>(initialSortField);
  const [sortDir, setSortDir] = useState<SortDir>(initialSortDir);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir(field === "airline_name" ? "asc" : "desc");
    }
  };

  const sorted = [...data].sort((a, b) => {
    const aVal = a[sortField] ?? -Infinity;
    const bVal = b[sortField] ?? -Infinity;
    if (typeof aVal === "string" && typeof bVal === "string") {
      return sortDir === "asc"
        ? aVal.localeCompare(bVal)
        : bVal.localeCompare(aVal);
    }
    return sortDir === "asc"
      ? (aVal as number) - (bVal as number)
      : (bVal as number) - (aVal as number);
  });

  // Sort the FULL data set first, then keep only the visible rows. This makes a
  // column sort rank the entire data set, never just the currently-shown rows.
  const visible = displayLimit != null ? sorted.slice(0, displayLimit) : sorted;

  const SortIcon = ({ field }: { field: SortField }) => {
    if (field !== sortField) return <ArrowUpDown className="h-3.5 w-3.5" />;
    return sortDir === "asc" ? (
      <ArrowUp className="h-3.5 w-3.5" />
    ) : (
      <ArrowDown className="h-3.5 w-3.5" />
    );
  };

  const colBtn = (field: SortField, label: string) => (
    <Button
      variant="ghost"
      size="sm"
      onClick={() => handleSort(field)}
      className={`h-auto p-0 font-semibold text-xs flex items-center gap-1 whitespace-normal leading-tight${
        field === sortField ? " border-2 border-foreground/80 rounded-sm px-1 py-0.5" : ""
      }`}
    >
      {label} <SortIcon field={field} />
    </Button>
  );

  const onTimeBadge = (pct: number) => {
    const cls =
      pct >= 85 ? "bg-success text-white" : pct >= 75 ? "bg-warning text-background" : "bg-destructive text-white";
    return <Badge className={`${cls} text-xs px-1 py-0`}>{pct.toFixed(1)}%</Badge>;
  };

  const cancelBadge = (pct: number) => {
    const cls =
      pct <= 2 ? "bg-success text-white" : pct <= 4 ? "bg-warning text-background" : "bg-destructive text-white";
    return <Badge className={`${cls} text-xs px-1 py-0`}>{pct.toFixed(1)}%</Badge>;
  };

  const displayCity = language === "he" && cityHe ? cityHe : city;
  const title = titleOverride ?? t("performance.tableTitle").replace("{city}", displayCity);

  return (
    <Card className="bg-gradient-to-br from-card to-secondary/50 border border-border/50 shadow-[var(--shadow-card)]">
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <PlaneTakeoff className="h-5 w-5 text-primary" />
          <CardTitle
            className="text-xl font-semibold text-foreground"
            style={language === "he" ? { fontFamily: "'Apple SD Gothic Neo', sans-serif", fontWeight: 800 } : undefined}
          >
            {title}
          </CardTitle>
        </div>
      </CardHeader>

      <CardContent className="p-0">
        {loading ? (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">
            {t("common.loading")}
          </p>
        ) : sorted.length === 0 ? (
          <p className="px-4 py-8 text-center text-sm text-muted-foreground">
            {t("performance.noResults")}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <Table className="w-full table-fixed">
              <TableHeader>
                <TableRow className="border-border/50">
                  <TableHead className="w-[30%] whitespace-normal break-words">
                    {colBtn("airline_name", t("airline.name"))}
                  </TableHead>
                  <TableHead className="w-[16%] text-center">
                    {colBtn("total_flights", t("performance.totalFlights"))}
                  </TableHead>
                  <TableHead className="w-[18%] text-center">
                    {colBtn("on_time_pct", t("performance.onTimePct"))}
                  </TableHead>
                  <TableHead className="w-[18%] text-center">
                    {colBtn("cancelled_pct", t("performance.cancelledPct"))}
                  </TableHead>
                  <TableHead className="w-[18%] text-center">
                    {colBtn("avg_delay_minutes_positive_only", t("performance.avgDelay"))}
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {visible.map((row, i) => (
                  <TableRow
                    key={`${row.airline_name}-${i}`}
                    className="border-border/30 hover:bg-muted/30 transition-colors"
                  >
                    <TableCell className="font-medium text-foreground px-2 py-2">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-muted-foreground">{i + 1}</span>
                        <span className="text-xs">{row.airline_name}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-center text-xs px-2 py-2">
                      {row.total_flights.toLocaleString()}
                    </TableCell>
                    <TableCell className="text-center px-2 py-2">
                      {onTimeBadge(row.on_time_pct)}
                    </TableCell>
                    <TableCell className="text-center px-2 py-2">
                      {cancelBadge(row.cancelled_pct)}
                    </TableCell>
                    <TableCell className="text-center text-xs px-2 py-2">
                      {row.avg_delay_minutes_positive_only != null
                        ? `${row.avg_delay_minutes_positive_only.toFixed(1)} ${t("performance.minutes")}`
                        : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
};
