"""
Central URL configuration for all API endpoints
Add new endpoints here to make them available across the application
"""

# Base API version
API_V1_PREFIX = "/api/v1"

# Health & Status URLs
ROOT_URL = "/"
HEALTH_URL = "/health"
READY_URL = "/ready"
METRICS_URL = "/metrics"

# Flight Data URLs
FLIGHTS_BASE_URL = f"{API_V1_PREFIX}/flights"
FLIGHTS_LIST_URL = f"{FLIGHTS_BASE_URL}/"
FLIGHTS_DETAIL_URL = FLIGHTS_BASE_URL + "/{flight_id}"
FLIGHTS_SEARCH_URL = f"{FLIGHTS_BASE_URL}/search"
FLIGHTS_STATS_URL = f"{FLIGHTS_BASE_URL}/stats"
FLIGHTS_AIRLINES_URL = f"{FLIGHTS_BASE_URL}/airlines"
FLIGHTS_DESTINATIONS_URL = f"{FLIGHTS_BASE_URL}/destinations"

# Example: New endpoint
FLIGHTS_DELAYS_URL = f"{FLIGHTS_BASE_URL}/delays"

# URL Groups for easy reference
HEALTH_URLS = {
    "root": ROOT_URL,
    "health": HEALTH_URL,
    "ready": READY_URL,
    "metrics": METRICS_URL,
}

FLIGHT_URLS = {
    "list": FLIGHTS_LIST_URL,
    "detail": FLIGHTS_DETAIL_URL,
    "search": FLIGHTS_SEARCH_URL,
    "stats": FLIGHTS_STATS_URL,
    "airlines": FLIGHTS_AIRLINES_URL,
    "destinations": FLIGHTS_DESTINATIONS_URL,
}

# All URLs in one place
ALL_URLS = {
    **HEALTH_URLS,
    **FLIGHT_URLS,
}

# For easy iteration
URL_LIST = list(ALL_URLS.values())
