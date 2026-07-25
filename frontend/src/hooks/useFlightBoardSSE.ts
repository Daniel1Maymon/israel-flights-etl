import { useState, useEffect } from 'react';
import { API_ENDPOINTS } from '@/config/api';

export interface FlightRow {
  flight_id: string;
  flight_number: string;
  airline_code: string;
  airline_name: string;
  direction: string;
  location_iata: string | null;
  location_en: string | null;
  location_he: string | null;
  location_city_en: string | null;
  country_en: string | null;
  terminal: string | null;
  scheduled_time: string | null;
  actual_time: string | null;
  status_en: string | null;
  status_he: string | null;
  delay_minutes: number | null;
}

export interface FlightBoardParams {
  direction: 'A' | 'D';
  sort_by: string;
  sort_order: 'asc' | 'desc';
  flight_number?: string;
  airline_code?: string;
  location?: string;
  terminal?: string;
  date_from?: string;
  date_to?: string;
}

interface UseFlightBoardSSEResult {
  flights: FlightRow[];
  /** Rows in the current payload — not the number of matching flights in the DB. */
  total: number;
  /** True when the window held more flights than the server will return. */
  truncated: boolean;
  loading: boolean;
  error: string | null;
  lastUpdated: Date | null;
}

export function useFlightBoardSSE(
  params: FlightBoardParams,
  isPaused: boolean,
): UseFlightBoardSSEResult {
  const [flights, setFlights] = useState<FlightRow[]>([]);
  const [total, setTotal] = useState(0);
  const [truncated, setTruncated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  useEffect(() => {
    setLoading(true);
    setFlights([]);

    if (isPaused) {
      setLoading(false);
      return;
    }

    const qs = new URLSearchParams();
    qs.set('direction', params.direction);
    qs.set('sort_by', params.sort_by);
    qs.set('sort_order', params.sort_order);
    if (params.flight_number) qs.set('flight_number', params.flight_number);
    if (params.airline_code) qs.set('airline_code', params.airline_code);
    if (params.location) qs.set('location', params.location);
    if (params.terminal) qs.set('terminal', params.terminal);
    if (params.date_from) qs.set('date_from', params.date_from);
    if (params.date_to) qs.set('date_to', params.date_to);

    const url = `${API_ENDPOINTS.FLIGHT_BOARD_STREAM}?${qs.toString()}`;
    const es = new EventSource(url);

    es.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === 'flights') {
          setFlights(msg.data);
          // Server sends `count` (rows in this payload). `total` was removed: it
          // reported the full matching-row count and so disclosed table size.
          setTotal(msg.count ?? msg.data.length);
          setTruncated(msg.truncated === true);
          setLastUpdated(new Date());
          setLoading(false);
          setError(null);
        } else if (msg.type === 'error') {
          setError(msg.message ?? 'Stream error');
          setLoading(false);
        }
      } catch {
        setError('Failed to parse server message');
        setLoading(false);
      }
    };

    es.onerror = () => {
      setError('Connection lost — reconnecting…');
      setLoading(false);
    };

    return () => {
      es.close();
    };
  }, [
    params.direction,
    params.sort_by,
    params.sort_order,
    params.flight_number,
    params.airline_code,
    params.location,
    params.terminal,
    params.date_from,
    params.date_to,
    isPaused,
  ]);

  return { flights, total, truncated, loading, error, lastUpdated };
}
