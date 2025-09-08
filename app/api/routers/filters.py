# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""Router for managing filter rules."""

import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.api.deps import get_database, get_current_user
from app.db.models import FilterRule, Channel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/filters", tags=["Filter Rules"])

# Pydantic schemas
class FilterRuleCreate(BaseModel):
    channel_id: int
    rule_type: str  # 'keyword', 'regex'
    pattern: str
    description: Optional[str] = None
    is_active: bool = True

class FilterRuleUpdate(BaseModel):
    rule_type: Optional[str] = None
    pattern: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class FilterRuleResponse(BaseModel):
    id: int
    channel_id: int
    rule_type: str
    pattern: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[FilterRuleResponse])
def list_filter_rules(
    skip: int = 0,
    limit: int = 100,
    channel_id: Optional[int] = None,
    active_only: bool = False,
    db: Session = Depends(get_database),
    current_user: str = Depends(get_current_user)
):
    """List filter rules with optional filtering."""
    query = db.query(FilterRule)
    
    if channel_id:
        query = query.filter(FilterRule.channel_id == channel_id)
    if active_only:
        query = query.filter(FilterRule.is_active == True)
    
    return query.offset(skip).limit(limit).all()

@router.post("/", response_model=FilterRuleResponse, status_code=status.HTTP_201_CREATED)
def create_filter_rule(
    rule_data: FilterRuleCreate,
    db: Session = Depends(get_database),
    current_user: str = Depends(get_current_user)
):
    """Create a new filter rule."""
    # Validate channel exists
    channel = db.query(Channel).filter(Channel.id == rule_data.channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {rule_data.channel_id} not found"
        )
    
    # Validate rule type
    if rule_data.rule_type not in ['keyword', 'regex']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rule type must be 'keyword' or 'regex'"
        )
    
    # Test regex pattern if applicable
    if rule_data.rule_type == 'regex':
        import re
        try:
            re.compile(rule_data.pattern)
        except re.error as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid regex pattern: {str(e)}"
            )
    
    rule = FilterRule(
        channel_id=rule_data.channel_id,
        rule_type=rule_data.rule_type,
        pattern=rule_data.pattern,
        description=rule_data.description,
        is_active=rule_data.is_active,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    logger.info(f"Created filter rule: {rule.rule_type} - {rule.pattern}")
    return rule

@router.get("/{rule_id}", response_model=FilterRuleResponse)
def get_filter_rule(
    rule_id: int,
    db: Session = Depends(get_database),
    current_user: str = Depends(get_current_user)
):
    """Get a specific filter rule."""
    rule = db.query(FilterRule).filter(FilterRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Filter rule with ID {rule_id} not found"
        )
    return rule

@router.put("/{rule_id}", response_model=FilterRuleResponse)
def update_filter_rule(
    rule_id: int,
    rule_data: FilterRuleUpdate,
    db: Session = Depends(get_database),
    current_user: str = Depends(get_current_user)
):
    """Update a filter rule."""
    rule = db.query(FilterRule).filter(FilterRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Filter rule with ID {rule_id} not found"
        )
    
    # Update fields if provided
    if rule_data.rule_type is not None:
        if rule_data.rule_type not in ['keyword', 'regex']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Rule type must be 'keyword' or 'regex'"
            )
        rule.rule_type = rule_data.rule_type
    
    if rule_data.pattern is not None:
        # Test regex if applicable
        if (rule_data.rule_type or rule.rule_type) == 'regex':
            import re
            try:
                re.compile(rule_data.pattern)
            except re.error as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid regex pattern: {str(e)}"
                )
        rule.pattern = rule_data.pattern
    
    if rule_data.description is not None:
        rule.description = rule_data.description
    if rule_data.is_active is not None:
        rule.is_active = rule_data.is_active
    
    rule.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(rule)
    
    logger.info(f"Updated filter rule {rule_id}")
    return rule

@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_filter_rule(
    rule_id: int,
    db: Session = Depends(get_database),
    current_user: str = Depends(get_current_user)
):
    """Delete a filter rule."""
    rule = db.query(FilterRule).filter(FilterRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Filter rule with ID {rule_id} not found"
        )
    
    db.delete(rule)
    db.commit()
    
    logger.info(f"Deleted filter rule {rule_id}")
