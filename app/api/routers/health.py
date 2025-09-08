"""Health check endpoint."""

from datetime import datetime, timezone
from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("/")
def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "tg-news-summarizer"
    }

@router.get("/live")
def liveness_check():
    """Kubernetes liveness probe endpoint."""
    return {"status": "alive"}

@router.get("/live")
def liveness_check():
    """
    Kubernetes liveness probe endpoint.
    
    Returns:
        Simple alive status
    """
    return {"status": "alive"}
