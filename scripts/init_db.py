#!/usr/bin/env python3
"""Database initialization script."""

import os
import sys
import subprocess
import logging

# Add the app directory to Python path
sys.path.insert(0, '/app')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_database():
    """Initialize database with proper migrations."""
    try:
        os.chdir('/app')
        
        # Check if migrations directory exists
        versions_dir = '/app/alembic/versions'
        if not os.path.exists(versions_dir):
            os.makedirs(versions_dir, exist_ok=True)
        
        # Check if any migration files exist
        migration_files = [f for f in os.listdir(versions_dir) if f.endswith('.py') and f != '__init__.py']
        
        if not migration_files:
            logger.info("No migration files found, creating initial migration...")
            # Create initial migration
            result = subprocess.run([
                sys.executable, "-m", "alembic", "revision", "--autogenerate", 
                "-m", "Initial tables"
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error(f"Failed to create migration: {result.stderr}")
                return False
            
            logger.info("Initial migration created successfully")
        
        # Apply migrations
        logger.info("Applying database migrations...")
        result = subprocess.run([
            sys.executable, "-m", "alembic", "upgrade", "head"
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info("Database migrations applied successfully")
            return True
        else:
            logger.error(f"Migration failed: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
