"""
Main API router that includes all endpoint modules
"""
from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.flights import router as flights_router
from app.api.airline_endpoints import router as airline_router
from app.api.destinations import router as destinations_router
from app.api.flight_board import router as flight_board_router
from app.api.ai_search import router as ai_search_router

# Create main API router
api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health_router)
api_router.include_router(flights_router)
api_router.include_router(airline_router)
api_router.include_router(destinations_router)
api_router.include_router(flight_board_router)
api_router.include_router(ai_search_router)
