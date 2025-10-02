"""
Legacy endpoints file - now redirects to the new API structure
This file is kept for backward compatibility
"""
from app.api.router import api_router

# Export the main router for backward compatibility
router = api_router
