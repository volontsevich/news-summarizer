"""Main API router that combines all endpoint modules."""

from fastapi import APIRouter

from app.api.v1 import channels, posts, alert_rules, filters, digests

api_router = APIRouter()

# Include all endpoint routers with prefixes
api_router.include_router(
    channels.router,
    prefix="/channels",
    tags=["channels"]
)

api_router.include_router(
    posts.router,
    prefix="/posts", 
    tags=["posts"]
)

api_router.include_router(
    alert_rules.router,
    prefix="/alert-rules",
    tags=["alert-rules"]
)

api_router.include_router(
    filters.router,
    prefix="/filters",
    tags=["filters"]
)

api_router.include_router(
    digests.router,
    prefix="/digests",
    tags=["digests"]
)


@api_router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "tg-news-summarizer",
        "version": "0.1.0"
    }


@api_router.get("/")
async def root():
    """API root endpoint with basic information."""
    return {
        "message": "TG News Summarizer API",
        "version": "0.1.0",
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "available_endpoints": {
            "channels": "/api/v1/channels",
            "posts": "/api/v1/posts", 
            "alert_rules": "/api/v1/alert-rules",
            "filters": "/api/v1/filters",
            "digests": "/api/v1/digests",
            "health": "/api/v1/health"
        }
    }
