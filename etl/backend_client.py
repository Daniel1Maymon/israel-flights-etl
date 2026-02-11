"""
Backend API client for ETL service.
Uses Railway Private Networking to communicate with Backend service.
"""
import logging
import requests
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class BackendClient:
    """Client for communicating with Backend API via Railway Private Networking"""

    def __init__(self, backend_url: Optional[str] = None):
        """
        Initialize backend client.

        Args:
            backend_url: Backend service URL from Railway Private Networking
                        Format: http://<service-name>.railway.internal:<port>
                        Example: http://backend.railway.internal:8000
        """
        self.backend_url = backend_url
        self.enabled = backend_url is not None

        if not self.enabled:
            logger.info("Backend communication disabled (BACKEND_PRIVATE_URL not set)")
        else:
            logger.info("Backend client initialized with URL: %s", backend_url)

    def health_check(self) -> bool:
        """
        Check if backend service is healthy.

        Returns:
            bool: True if backend is healthy, False otherwise
        """
        if not self.enabled:
            return False

        try:
            response = requests.get(
                f"{self.backend_url}/health",
                timeout=5
            )
            response.raise_for_status()
            logger.info("Backend health check successful")
            return True
        except requests.RequestException as e:
            logger.error("Backend health check failed: %s", str(e))
            return False

    def notify_etl_complete(self, records_processed: int) -> bool:
        """
        Notify backend that ETL run completed.

        Args:
            records_processed: Number of records processed in ETL run

        Returns:
            bool: True if notification successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            payload = {
                "event": "etl_complete",
                "records_processed": records_processed
            }
            response = requests.post(
                f"{self.backend_url}/api/v1/etl/notify",
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            logger.info("Successfully notified backend of ETL completion")
            return True
        except requests.RequestException as e:
            logger.error("Failed to notify backend: %s", str(e))
            return False

    def trigger_cache_refresh(self) -> bool:
        """
        Trigger backend to refresh its cache after ETL updates.

        Returns:
            bool: True if cache refresh successful, False otherwise
        """
        if not self.enabled:
            return False

        try:
            response = requests.post(
                f"{self.backend_url}/api/v1/cache/refresh",
                timeout=10
            )
            response.raise_for_status()
            logger.info("Successfully triggered backend cache refresh")
            return True
        except requests.RequestException as e:
            logger.error("Failed to trigger cache refresh: %s", str(e))
            return False

    def send_request(
        self,
        endpoint: str,
        method: str = "GET",
        data: Optional[Dict[str, Any]] = None,
        timeout: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Send a generic request to backend API.

        Args:
            endpoint: API endpoint path (e.g., "/api/v1/flights")
            method: HTTP method (GET, POST, PUT, DELETE)
            data: Request payload for POST/PUT requests
            timeout: Request timeout in seconds

        Returns:
            Response JSON data if successful, None otherwise
        """
        if not self.enabled:
            logger.warning("Backend client not enabled, skipping request")
            return None

        try:
            url = f"{self.backend_url}{endpoint}"
            response = requests.request(
                method=method,
                url=url,
                json=data if method in ["POST", "PUT"] else None,
                timeout=timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error("Backend request failed [%s %s]: %s", method, endpoint, str(e))
            return None
