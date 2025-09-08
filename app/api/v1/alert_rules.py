"""Alert rules management API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import crud as alert_rule_crud
from app.db.models import AlertRule

router = APIRouter()


@router.get("/", response_model=List[dict])
async def list_alert_rules(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    enabled: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    """List all alert rules."""
    query = db.query(AlertRule)
    
    if enabled is not None:
        query = query.filter(AlertRule.enabled == enabled)
    
    rules = query.offset(skip).limit(limit).all()
    
    return [
        {
            "id": str(rule.id),
            "name": rule.name,
            "pattern": rule.pattern,
            "email_to": rule.email_to,
            "is_regex": rule.is_regex,
            "enabled": rule.enabled,
            "language": rule.language,
            "created_at": rule.created_at.isoformat()
        }
        for rule in rules
    ]


@router.post("/")
async def create_alert_rule(
    name: str = Query(..., description="Alert rule name"),
    pattern: str = Query(..., description="Alert pattern (keywords, regex, etc.)"),
    email_to: str = Query(..., description="Email to send alerts to"),
    is_regex: bool = Query(False, description="Whether the pattern is regex"),
    enabled: bool = Query(True, description="Whether the rule is enabled"),
    language: str = Query(None, description="Language filter"),
    db: Session = Depends(get_db)
):
    """Create a new alert rule."""
    try:
        # Validate email format (basic validation)
        if "@" not in email_to:
            raise HTTPException(status_code=400, detail="Invalid email format")
        
        rule = AlertRule(
            name=name,
            pattern=pattern,
            email_to=email_to,
            is_regex=is_regex,
            enabled=enabled,
            language=language
        )
        
        db.add(rule)
        db.commit()
        db.refresh(rule)
        
        return {
            "id": str(rule.id),
            "name": rule.name,
            "pattern": rule.pattern,
            "email_to": rule.email_to,
            "is_regex": rule.is_regex,
            "enabled": rule.enabled,
            "language": rule.language,
            "created_at": rule.created_at.isoformat(),
            "message": "Alert rule created successfully!"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create alert rule: {str(e)}")


@router.get("/{rule_id}")
async def get_alert_rule(
    rule_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific alert rule by ID."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    
    return {
        "id": str(rule.id),
        "name": rule.name,
        "keywords": rule.keywords,
        "email": rule.email,
        "is_active": rule.is_active,
        "created_at": rule.created_at.isoformat(),
        "updated_at": rule.updated_at.isoformat(),
        "last_triggered": rule.last_triggered.isoformat() if rule.last_triggered else None
    }


@router.put("/{rule_id}")
async def update_alert_rule(
    rule_id: str,
    name: Optional[str] = Query(None, description="Alert rule name"),
    keywords: Optional[str] = Query(None, description="Comma-separated keywords"),
    email: Optional[str] = Query(None, description="Email to send alerts to"),
    is_active: Optional[bool] = Query(None, description="Whether the rule is active"),
    db: Session = Depends(get_db)
):
    """Update an alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    
    try:
        if name is not None:
            rule.name = name
        if keywords is not None:
            rule.keywords = keywords
        if email is not None:
            if "@" not in email:
                raise HTTPException(status_code=400, detail="Invalid email format")
            rule.email = email
        if is_active is not None:
            rule.is_active = is_active
        
        db.commit()
        db.refresh(rule)
        
        return {
            "id": str(rule.id),
            "name": rule.name,
            "keywords": rule.keywords,
            "email": rule.email,
            "is_active": rule.is_active,
            "updated_at": rule.updated_at.isoformat(),
            "message": "Alert rule updated successfully!"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update alert rule: {str(e)}")


@router.delete("/{rule_id}")
async def delete_alert_rule(
    rule_id: str,
    db: Session = Depends(get_db)
):
    """Delete an alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    
    try:
        db.delete(rule)
        db.commit()
        return {"message": "Alert rule deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete alert rule: {str(e)}")


@router.post("/{rule_id}/activate")
async def activate_alert_rule(
    rule_id: str,
    db: Session = Depends(get_db)
):
    """Activate an alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    
    if rule.is_active:
        raise HTTPException(status_code=400, detail="Alert rule is already active")
    
    try:
        rule.is_active = True
        db.commit()
        return {"message": "Alert rule activated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to activate alert rule: {str(e)}")


@router.post("/{rule_id}/deactivate")
async def deactivate_alert_rule(
    rule_id: str,
    db: Session = Depends(get_db)
):
    """Deactivate an alert rule."""
    rule = db.query(AlertRule).filter(AlertRule.id == rule_id).first()
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    
    if not rule.is_active:
        raise HTTPException(status_code=400, detail="Alert rule is already inactive")
    
    try:
        rule.is_active = False
        db.commit()
        return {"message": "Alert rule deactivated successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to deactivate alert rule: {str(e)}")


@router.get("/stats/")
async def get_alert_stats(
    db: Session = Depends(get_db)
):
    """Get alert rule statistics."""
    try:
        total_rules = db.query(AlertRule).count()
        active_rules = db.query(AlertRule).filter(AlertRule.is_active == True).count()
        
        # Get recently triggered rules (in last 24 hours)
        from datetime import datetime, timedelta
        recent_cutoff = datetime.utcnow() - timedelta(days=1)
        recently_triggered = db.query(AlertRule).filter(
            AlertRule.last_triggered >= recent_cutoff
        ).count()
        
        return {
            "total_rules": total_rules,
            "active_rules": active_rules,
            "inactive_rules": total_rules - active_rules,
            "recently_triggered_24h": recently_triggered,
            "activation_rate": (active_rules / total_rules * 100) if total_rules > 0 else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving stats: {str(e)}")
