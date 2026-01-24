// API configuration
// In Vite, environment variables must be prefixed with VITE_
// Access via import.meta.env.VITE_API_URL
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export const API_ENDPOINTS = {
  FLIGHTS: `${API_BASE_URL}/api/v1/flights`,
  AIRLINES_STATS: `${API_BASE_URL}/api/v1/airlines/stats`,
  AIRLINE_DESTINATIONS: (airline: string) => `${API_BASE_URL}/api/v1/airlines/${encodeURIComponent(airline)}/destinations`,
  DESTINATIONS: `${API_BASE_URL}/api/v1/destinations`,
  AIRLINES: `${API_BASE_URL}/api/v1/flights/airlines`,
};
