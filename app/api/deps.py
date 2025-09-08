# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""FastAPI dependencies for authentication, DB, etc."""

from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.config import get_settings
import secrets

security = HTTPBasic()

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    """
    Simple HTTP Basic Auth dependency.
    
    Args:
        credentials: HTTP Basic Auth credentials
        
    Returns:
        Username if authenticated
        
    Raises:
        HTTPException: If authentication fails
    """
    settings = get_settings()
    
    # Check if API authentication is configured
    if not settings.API_USERNAME or not settings.API_PASSWORD:
        # If no auth configured, allow access (for development)
        return "anonymous"
    
    # Verify credentials
    is_correct_username = secrets.compare_digest(
        credentials.username, settings.API_USERNAME
    )
    is_correct_password = secrets.compare_digest(
        credentials.password, settings.API_PASSWORD
    )
    
    if not (is_correct_username and is_correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    
    return credentials.username

def get_database() -> Generator[Session, None, None]:
    """
    Database dependency.
    
    Yields:
        SQLAlchemy session
    """
    yield from get_db()

# Type alias for dependency injection
DatabaseDep = Generator[Session, None, None]
UserDep = str
