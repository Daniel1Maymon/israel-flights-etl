#!/usr/bin/env python3
"""
Database initialization script
Creates all tables defined in the models
"""

import sys
import os
sys.path.append('/app')

from app.database import engine, Base
from app.models.flight import Flight
import structlog

logger = structlog.get_logger()

def create_tables():
    """Create all database tables"""
    try:
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except Exception as e:
        logger.error("Failed to create database tables", error=str(e))
        return False

if __name__ == "__main__":
    success = create_tables()
    sys.exit(0 if success else 1)
