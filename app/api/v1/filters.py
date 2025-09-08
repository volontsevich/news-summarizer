"""Content filter management API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.db import crud as filter_crud
from app.db.models import FilterRule

router = APIRouter()


@router.get("/", response_model=List[dict])
async def list_filters(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    is_active: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    """List all content filters."""
    query = db.query(FilterRule)
    
    if is_active is not None:
        query = query.filter(FilterRule.enabled == is_active)
    
    filters = query.offset(skip).limit(limit).all()
    
    return [
        {
            "id": str(f.id),
            "name": f.name,
            "pattern": f.pattern,
            "is_regex": f.is_regex,
            "is_blocklist": f.is_blocklist,
            "enabled": f.enabled,
            "language": f.language,
            "created_at": f.created_at.isoformat()
        }
        for f in filters
    ]


@router.post("/")
async def create_filter(
    name: str = Query(..., description="Filter name"),
    pattern: str = Query(..., description="Filter pattern (keywords, regex, etc.)"),
    is_regex: bool = Query(False, description="Whether the pattern is regex"),
    is_blocklist: bool = Query(True, description="Whether this is a blocklist (True) or allowlist (False)"),
    enabled: bool = Query(True, description="Whether the filter is enabled"),
    language: str = Query(None, description="Language filter"),
    db: Session = Depends(get_db)
):
    """Create a new content filter."""
    try:
        filter_rule = FilterRule(
            name=name,
            pattern=pattern,
            is_regex=is_regex,
            is_blocklist=is_blocklist,
            enabled=enabled,
            language=language
        )
        
        db.add(filter_rule)
        db.commit()
        db.refresh(filter_rule)
        
        return {
            "id": str(filter_rule.id),
            "name": filter_rule.name,
            "pattern": filter_rule.pattern,
            "is_regex": filter_rule.is_regex,
            "is_blocklist": filter_rule.is_blocklist,
            "enabled": filter_rule.enabled,
            "language": filter_rule.language,
            "created_at": filter_rule.created_at.isoformat(),
            "message": "Filter created successfully!"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create filter: {str(e)}")


@router.get("/{filter_id}")
async def get_filter(
    filter_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific filter by ID."""
    filter_rule = db.query(FilterRule).filter(FilterRule.id == filter_id).first()
    if not filter_rule:
        raise HTTPException(status_code=404, detail="Filter not found")
    
    return {
        "id": str(filter_rule.id),
        "name": filter_rule.name,
        "pattern": filter_rule.pattern,
        "is_regex": filter_rule.is_regex,
        "is_blocklist": filter_rule.is_blocklist,
        "enabled": filter_rule.enabled,
        "language": filter_rule.language,
        "created_at": filter_rule.created_at.isoformat()
    }


@router.delete("/{filter_id}")
async def delete_filter(
    filter_id: str,
    db: Session = Depends(get_db)
):
    """Delete a filter."""
    filter_rule = db.query(FilterRule).filter(FilterRule.id == filter_id).first()
    if not filter_rule:
        raise HTTPException(status_code=404, detail="Filter not found")
    
    try:
        db.delete(filter_rule)
        db.commit()
        return {"message": "Filter deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete filter: {str(e)}")


@router.post("/{filter_id}/test")
async def test_filter(
    filter_id: str,
    test_text: str = Query(..., description="Text to test the filter against"),
    db: Session = Depends(get_db)
):
    """Test a filter against sample text."""
    filter_rule = db.query(FilterRule).filter(FilterRule.id == filter_id).first()
    if not filter_rule:
        raise HTTPException(status_code=404, detail="Filter not found")
    
    try:
        # Simple pattern matching for testing
        if filter_rule.filter_type == "keyword":
            keywords = [kw.strip().lower() for kw in filter_rule.pattern.split(',')]
            test_text_lower = test_text.lower()
            matches = [kw for kw in keywords if kw in test_text_lower]
            would_match = len(matches) > 0
        else:
            # For regex and other types, simple contains check for now
            would_match = filter_rule.pattern.lower() in test_text.lower()
            matches = [filter_rule.pattern] if would_match else []
        
        return {
            "filter_id": filter_id,
            "filter_name": filter_rule.name,
            "filter_type": filter_rule.filter_type,
            "pattern": filter_rule.pattern,
            "test_text": test_text[:200] + "..." if len(test_text) > 200 else test_text,
            "would_match": would_match,
            "matches": matches
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Filter test failed: {str(e)}")


@router.get("/stats/")
async def get_filter_stats(
    db: Session = Depends(get_db)
):
    """Get filter statistics."""
    try:
        total_filters = db.query(FilterRule).count()
        active_filters = db.query(FilterRule).filter(FilterRule.enabled == True).count()
        
        # Get filter type distribution by is_regex
        regex_filters = db.query(FilterRule).filter(FilterRule.is_regex == True).count()
        keyword_filters = total_filters - regex_filters
        
        # Get blocklist vs allowlist
        blocklist_filters = db.query(FilterRule).filter(FilterRule.is_blocklist == True).count()
        allowlist_filters = total_filters - blocklist_filters
        
        return {
            "total_filters": total_filters,
            "active_filters": active_filters,
            "inactive_filters": total_filters - active_filters,
            "regex_filters": regex_filters,
            "keyword_filters": keyword_filters,
            "blocklist_filters": blocklist_filters,
            "allowlist_filters": allowlist_filters,
            "activation_rate": (active_filters / total_filters * 100) if total_filters > 0 else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving stats: {str(e)}")
