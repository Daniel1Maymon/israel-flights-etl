import { useState, useEffect, useCallback } from 'react';
import { Plane, Pause, Play, ChevronUp, ChevronDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { useLanguage } from '@/contexts/LanguageContext';
import { useFlightBoardSSE, type FlightBoardParams, type FlightRow } from '@/hooks/useFlightBoardSSE';
import { API_ENDPOINTS } from '@/config/api';
import { PageLayout } from '@/components/PageLayout';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface FilterOptions {
  airlines: { code: string; name: string }[];
  cities: string[];
  terminals: string[];
}

interface FilterState {
  flightNumber: string;
  airlineCode: string;
  location: string;
  terminal: string;
  dateFrom: string;
  dateTo: string;
}

const EMPTY_FILTERS: FilterState = {
  flightNumber: '',
  airlineCode: '',
  location: '',
  terminal: '',
  dateFrom: '',
  dateTo: '',
};

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------

const STATUS_EN_MAP: Record<string, string> = {
  landed: 'board.status.landed',
  arriving: 'board.status.arriving',
  final: 'board.status.final',
  cancelled: 'board.status.cancelled',
  canceled: 'board.status.cancelled',
  delayed: 'board.status.delayed',
  'on time': 'board.status.onTime',
  departed: 'board.status.departed',
  boarding: 'board.status.boarding',
  'gate open': 'board.status.gateOpen',
  'gate close': 'board.status.gateClose',
  'gate closed': 'board.status.gateClose',
  taxiing: 'board.status.taxiing',
};

function getStatusBadgeClass(statusEn: string | null): string {
  const s = (statusEn ?? '').toLowerCase();
  if (s.includes('cancel')) return 'bg-destructive/15 text-destructive border-destructive/30';
  if (s.includes('delay') || s.includes('late')) return 'bg-warning/15 text-warning border-warning/30';
  if (s.includes('land') || s.includes('arriv')) return 'bg-success/15 text-success border-success/30';
  if (s.includes('board') || s.includes('gate')) return 'bg-info/15 text-info border-info/30';
  if (s.includes('depart') || s.includes('taxi')) return 'bg-primary/15 text-primary border-primary/30';
  if (s.includes('final')) return 'bg-orange-500/15 text-orange-500 border-orange-500/30';
  return 'bg-muted/50 text-muted-foreground border-border';
}

function isDelayed(flight: FlightRow): boolean {
  if (!flight.scheduled_time || !flight.actual_time) return false;
  return new Date(flight.actual_time) > new Date(flight.scheduled_time);
}

// ---------------------------------------------------------------------------
// Time format
// ---------------------------------------------------------------------------

const IL_TZ = 'Asia/Jerusalem';

function formatTime(iso: string | null, language: string): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString(language === 'he' ? 'he-IL' : 'en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: IL_TZ,
  });
}

function formatDate(iso: string | null): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('en-GB', {
    day: '2-digit',
    month: '2-digit',
    timeZone: IL_TZ,
  });
}

// ---------------------------------------------------------------------------
// SortIcon
// ---------------------------------------------------------------------------

function SortIcon({ field, current, dir }: { field: string; current: string; dir: 'asc' | 'desc' }) {
  if (field !== current) return <ChevronUp className="h-3 w-3 opacity-20" />;
  return dir === 'asc'
    ? <ChevronUp className="h-3 w-3 text-primary" />
    : <ChevronDown className="h-3 w-3 text-primary" />;
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

const FlightBoard = () => {
  const { t, language } = useLanguage();

  const [tab, setTab] = useState<'A' | 'D'>('A');
  const [draftFilters, setDraftFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [appliedFilters, setAppliedFilters] = useState<FilterState>(EMPTY_FILTERS);
  const [filterOptions, setFilterOptions] = useState<FilterOptions>({ airlines: [], cities: [], terminals: [] });
  const [isPaused, setIsPaused] = useState(false);
  const [sortBy, setSortBy] = useState('scheduled_time');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');

  // Build SSE params object
  const sseParams: FlightBoardParams = {
    direction: tab,
    sort_by: sortBy,
    sort_order: sortDir,
    flight_number: appliedFilters.flightNumber || undefined,
    airline_code: appliedFilters.airlineCode || undefined,
    location: appliedFilters.location || undefined,
    terminal: appliedFilters.terminal || undefined,
    date_from: appliedFilters.dateFrom || undefined,
    date_to: appliedFilters.dateTo || undefined,
  };

  const { flights, total, truncated, loading, error, lastUpdated } = useFlightBoardSSE(sseParams, isPaused);

  // Fetch filter options whenever tab changes
  useEffect(() => {
    fetch(`${API_ENDPOINTS.FLIGHT_BOARD_OPTIONS}?direction=${tab}`)
      .then((r) => {
        if (!r.ok) return null;
        return r.json();
      })
      .then((data: FilterOptions | null) => {
        if (data && Array.isArray(data.airlines)) setFilterOptions(data);
      })
      .catch(() => {/* ignore — dropdowns stay empty until backend is reachable */});
  }, [tab]);

  const handleSearch = useCallback(() => {
    setAppliedFilters({ ...draftFilters });
  }, [draftFilters]);

  const handleClear = useCallback(() => {
    setDraftFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
  }, []);

  const handleTabChange = (newTab: 'A' | 'D') => {
    setTab(newTab);
    setDraftFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
  };

  const handleSort = (field: string) => {
    if (sortBy === field) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortBy(field);
      setSortDir('asc');
    }
  };

  const handleKeyDown = (e: { key: string }) => {
    if (e.key === 'Enter') handleSearch();
  };

  const cityLabel = tab === 'A' ? t('board.col.from') : t('board.col.to');

  const formattedLastUpdated = lastUpdated
    ? lastUpdated.toLocaleTimeString(language === 'he' ? 'he-IL' : 'en-GB', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      })
    : null;

  // ---------------------------------------------------------------------------
  // Status display
  // ---------------------------------------------------------------------------

  const displayStatus = (flight: FlightRow) => {
    // Prefer Hebrew status in Hebrew mode
    if (language === 'he' && flight.status_he) return flight.status_he;

    const raw = (flight.status_en ?? '').toLowerCase();
    const key = STATUS_EN_MAP[raw];
    if (key) return t(key);
    return flight.status_en ?? '—';
  };

  // ---------------------------------------------------------------------------
  // Sortable column header
  // ---------------------------------------------------------------------------

  const Th = ({
    field,
    children,
    className = '',
  }: {
    field: string;
    children: React.ReactNode;
    className?: string;
  }) => (
    <th
      className={`px-3 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide cursor-pointer select-none hover:text-foreground whitespace-nowrap ${className}`}
      onClick={() => handleSort(field)}
    >
      <span className="inline-flex items-center gap-1">
        {children}
        <SortIcon field={field} current={sortBy} dir={sortDir} />
      </span>
    </th>
  );

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <PageLayout width="wide">
        {/* ── Page header ── */}
        <div className="flex flex-wrap items-start justify-between gap-3 mb-6">
          <div>
            <h1 className="text-2xl font-bold text-foreground">{t('board.title')}</h1>
            <p className="text-sm text-muted-foreground mt-0.5">{t('board.airport')}</p>
          </div>

          {/* Last updated + pause */}
          <div className="flex flex-col items-start sm:items-end gap-1 text-sm">
            {formattedLastUpdated ? (
              <span className="text-muted-foreground">
                {t('board.lastUpdated')} <span className="font-mono font-semibold text-foreground">{formattedLastUpdated}</span>
                {total > 0 && (
                  <span className="ms-2 text-xs text-muted-foreground">
                    ({truncated ? `${total}+` : total} {tab === 'A' ? t('board.arrivals') : t('board.departures')})
                  </span>
                )}
              </span>
            ) : loading ? (
              <span className="text-muted-foreground text-xs">{t('board.connecting')}</span>
            ) : null}
            <Button
              variant="outline"
              size="sm"
              className="flex items-center gap-1.5 text-xs h-7"
              onClick={() => setIsPaused((p) => !p)}
            >
              {isPaused
                ? <><Play className="h-3 w-3" />{t('board.resumeRefresh')}</>
                : <><Pause className="h-3 w-3" />{t('board.pauseRefresh')}</>}
            </Button>
          </div>
        </div>

        {/* ── Tabs ── */}
        <div className="flex gap-1 mb-5 border-b border-border">
          {(['A', 'D'] as const).map((dir) => (
            <button
              key={dir}
              onClick={() => handleTabChange(dir)}
              className={`flex items-center gap-2 px-5 py-2.5 text-sm font-medium border-b-2 transition-colors -mb-px ${
                tab === dir
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              <Plane className={`h-4 w-4 ${dir === 'D' ? 'rotate-45' : '-rotate-45'}`} />
              {dir === 'A' ? t('board.arrivals') : t('board.departures')}
            </button>
          ))}
        </div>

        {/* ── Filter panel ── */}
        <div className="rounded-lg border border-border bg-card p-4 mb-5 space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {/* Flight number */}
            <Input
              placeholder={t('board.flightNumber')}
              value={draftFilters.flightNumber}
              onChange={(e) => setDraftFilters((f) => ({ ...f, flightNumber: e.target.value }))}
              onKeyDown={handleKeyDown}
              className="h-9 text-sm"
            />

            {/* Airline */}
            <Select
              value={draftFilters.airlineCode || '__all__'}
              onValueChange={(v) =>
                setDraftFilters((f) => ({ ...f, airlineCode: v === '__all__' ? '' : v }))
              }
            >
              <SelectTrigger className="h-9 text-sm">
                <SelectValue placeholder={t('board.allAirlines')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">{t('board.allAirlines')}</SelectItem>
                {(filterOptions.airlines ?? []).map((a) => (
                  <SelectItem key={a.code} value={a.code}>
                    {a.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* City */}
            <Select
              value={draftFilters.location || '__all__'}
              onValueChange={(v) =>
                setDraftFilters((f) => ({ ...f, location: v === '__all__' ? '' : v }))
              }
            >
              <SelectTrigger className="h-9 text-sm">
                <SelectValue placeholder={t('board.allCities')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">{t('board.allCities')}</SelectItem>
                {(filterOptions.cities ?? []).map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* Terminal */}
            <Select
              value={draftFilters.terminal || '__all__'}
              onValueChange={(v) =>
                setDraftFilters((f) => ({ ...f, terminal: v === '__all__' ? '' : v }))
              }
            >
              <SelectTrigger className="h-9 text-sm">
                <SelectValue placeholder={t('board.allTerminals')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">{t('board.allTerminals')}</SelectItem>
                {(filterOptions.terminals ?? []).map((term) => (
                  <SelectItem key={term} value={term}>
                    {t('board.terminal')} {term}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>

            {/* From date */}
            <Input
              type="date"
              placeholder={t('board.fromDate')}
              value={draftFilters.dateFrom}
              onChange={(e) => setDraftFilters((f) => ({ ...f, dateFrom: e.target.value }))}
              onKeyDown={handleKeyDown}
              className="h-9 text-sm"
            />

            {/* To date */}
            <Input
              type="date"
              placeholder={t('board.toDate')}
              value={draftFilters.dateTo}
              onChange={(e) => setDraftFilters((f) => ({ ...f, dateTo: e.target.value }))}
              onKeyDown={handleKeyDown}
              className="h-9 text-sm"
            />
          </div>

          <div className="flex gap-2">
            <Button size="sm" onClick={handleSearch} className="px-6">
              {t('board.search')}
            </Button>
            <Button size="sm" variant="outline" onClick={handleClear}>
              {t('board.clear')}
            </Button>
          </div>
        </div>

        {/* ── Error banner ── */}
        {error && (
          <div className="rounded-md bg-destructive/10 border border-destructive/30 text-destructive text-sm px-4 py-2 mb-4">
            {error}
          </div>
        )}

        {/* ── Table — all flights, vertically scrollable ── */}
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <div className="overflow-x-auto overflow-y-auto max-h-[calc(100vh-22rem)]">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 border-b border-border sticky top-0 z-10">
                <tr>
                  <Th field="airline_name">{t('board.col.airline')}</Th>
                  <Th field="flight_number">{t('board.col.flight')}</Th>
                  <th className="px-3 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide text-start whitespace-nowrap">
                    {cityLabel}
                  </th>
                  <th className="px-3 py-3 text-xs font-semibold text-muted-foreground uppercase tracking-wide text-start whitespace-nowrap">
                    {t('board.col.terminal')}
                  </th>
                  <Th field="scheduled_time">{t('board.col.scheduled')}</Th>
                  <Th field="actual_time">{t('board.col.updated')}</Th>
                  <Th field="status_en">{t('board.col.status')}</Th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {loading && flights.length === 0 ? (
                  // Skeleton rows
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i} className="animate-pulse">
                      {Array.from({ length: 7 }).map((__, j) => (
                        <td key={j} className="px-3 py-3">
                          <div className="h-4 rounded bg-muted" style={{ width: `${60 + Math.random() * 30}%` }} />
                        </td>
                      ))}
                    </tr>
                  ))
                ) : flights.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-16 text-center text-muted-foreground">
                      {t('board.noFlights')}
                    </td>
                  </tr>
                ) : (
                  flights.map((flight) => {
                    const delayed = isDelayed(flight);
                    const city = language === 'he' && flight.location_he
                      ? flight.location_he
                      : (flight.location_en ?? flight.location_city_en ?? '—');

                    return (
                      <tr
                        key={flight.flight_id}
                        className={`transition-colors hover:bg-muted/30 ${
                          delayed ? 'bg-warning/5' : ''
                        }`}
                      >
                        {/* Airline */}
                        <td className="px-3 py-3 font-medium text-foreground whitespace-nowrap">
                          {flight.airline_name ?? flight.airline_code ?? '—'}
                        </td>

                        {/* Flight number */}
                        <td className="px-3 py-3 font-mono text-foreground whitespace-nowrap">
                          {flight.flight_number ?? '—'}
                        </td>

                        {/* City */}
                        <td className="px-3 py-3 text-foreground">{city}</td>

                        {/* Terminal */}
                        <td className="px-3 py-3 text-center">
                          {flight.terminal ? (
                            <span className="inline-flex items-center justify-center w-7 h-7 rounded-full bg-muted text-muted-foreground text-xs font-medium">
                              {flight.terminal}
                            </span>
                          ) : '—'}
                        </td>

                        {/* Scheduled */}
                        <td className="px-3 py-3 font-mono text-foreground whitespace-nowrap">
                          <div>{formatTime(flight.scheduled_time, language)}</div>
                          {formatDate(flight.scheduled_time) && (
                            <div className="text-xs text-muted-foreground mt-0.5">
                              {formatDate(flight.scheduled_time)}
                            </div>
                          )}
                        </td>

                        {/* Actual / Updated */}
                        <td className={`px-3 py-3 font-mono whitespace-nowrap ${delayed ? 'text-warning font-semibold' : 'text-foreground'}`}>
                          {formatTime(flight.actual_time, language)}
                        </td>

                        {/* Status */}
                        <td className="px-3 py-3">
                          <span
                            className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${getStatusBadgeClass(flight.status_en)}`}
                          >
                            {displayStatus(flight)}
                          </span>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
    </PageLayout>
  );
};

export default FlightBoard;
