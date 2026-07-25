// API configuration
// In Vite, environment variables must be prefixed with VITE_
// Access via import.meta.env.VITE_API_URL
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const API_ENDPOINTS = {
  FLIGHTS: `${API_BASE_URL}/api/v1/flights`,
  AIRLINES_STATS: `${API_BASE_URL}/api/v1/airlines/stats`,
  AIRLINES_TOP_BOTTOM: `${API_BASE_URL}/api/v1/airlines/top-bottom`,
  AIRLINES_TOP_ON_TIME: `${API_BASE_URL}/api/v1/airlines/top-on-time`,
  /** @deprecated Unused. Its backend handler uses a 20-minute on-time window, a non-canonical
   *  cancellation match, and groups by country in Hebrew but city in English, so its numbers
   *  disagree with the rest of the site. Use AIRLINE_ROUTES instead. */
  AIRLINE_DESTINATIONS: (airline: string) => `${API_BASE_URL}/api/v1/airlines/${encodeURIComponent(airline)}/destinations`,
  AIRLINE_DIRECTORY: `${API_BASE_URL}/api/v1/airlines/directory`,
  AIRLINE_PROFILE: (airline: string) => `${API_BASE_URL}/api/v1/airlines/${encodeURIComponent(airline)}/profile`,
  AIRLINE_ROUTES: (airline: string) => `${API_BASE_URL}/api/v1/airlines/${encodeURIComponent(airline)}/routes`,
  DESTINATIONS: `${API_BASE_URL}/api/v1/destinations`,
  DESTINATION_CITIES: `${API_BASE_URL}/api/v1/destinations/cities`,
  DESTINATION_AIRLINE_PERFORMANCE: `${API_BASE_URL}/api/v1/destinations/airline-performance`,
  AIRLINES: `${API_BASE_URL}/api/v1/flights/airlines`,
  FLIGHT_BOARD_STREAM: `${API_BASE_URL}/api/v1/flight-board/stream`,
  FLIGHT_BOARD_OPTIONS: `${API_BASE_URL}/api/v1/flight-board/options`,
  AI_SEARCH: `${API_BASE_URL}/api/v1/ai-search`,
  ADMIN_METRICS: `${API_BASE_URL}/api/v1/admin/metrics`,
  ADMIN_EVENTS: `${API_BASE_URL}/api/v1/admin/events`,
  STATS_OVERVIEW: `${API_BASE_URL}/api/v1/stats/overview`,
  INSIGHTS_MONTHLY: `${API_BASE_URL}/api/v1/insights/monthly-by-nationality`,
  INSIGHTS_WEEKDAY: `${API_BASE_URL}/api/v1/insights/by-weekday`,
  INSIGHTS_HOUR: `${API_BASE_URL}/api/v1/insights/by-hour`,
  INSIGHTS_RECOVERY: `${API_BASE_URL}/api/v1/insights/carrier-recovery`,
};
