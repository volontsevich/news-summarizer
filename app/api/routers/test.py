"""Simple test router."""

from fastapi import APIRouter

router = APIRouter(prefix="/test", tags=["Test"])

@router.get("/")
def test_endpoint():
    """Test endpoint."""
    return {"message": "Test successful"}
