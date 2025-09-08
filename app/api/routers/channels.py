# NOTE FOR COPILOT:
# - Do not hard-code secrets. Read from app.core.config.Settings.
# - Use type hints, docstrings, structured logging, and retries where appropriate.
# - Keep functions small/testable. No global state.
# - Regex with re.IGNORECASE and safe timeouts.
# - Enforce LLM token limits/chunking; never send secrets.
# - Use DB sessions from app.db.session; commit safely.
# - Respect cron settings from env for schedules.

"""Router for managing Telegram channels."""

import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from app.api.deps import get_database, get_current_user
from app.db.models import Channel, Post
from app.tasks.ingest import ingest_single_channel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channels", tags=["Channels"])

# Pydantic schemas
class ChannelCreate(BaseModel):
    name: str
    username: str
    description: Optional[str] = None
    is_active: bool = True

class ChannelUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None

class ChannelResponse(BaseModel):
    id: int
    name: str
    username: str
    description: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class ChannelStats(BaseModel):
    channel_id: int
    channel_name: str
    total_posts: int
    posts_last_24h: int
    last_post_date: Optional[datetime]

@router.get("/", response_model=List[ChannelResponse])
def list_channels(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    db: Session = Depends(get_database),
    current_user: str = Depends(get_current_user)
):
    """
    List all channels with pagination.
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        active_only: Filter to active channels only
        db: Database session
        current_user: Authenticated user
        
    Returns:
        List of channels
    """
    query = db.query(Channel)
    
    if active_only:
        query = query.filter(Channel.is_active == True)
    
    channels = query.offset(skip).limit(limit).all()
    return channels

@router.post("/", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
def create_channel(
    channel_data: ChannelCreate,
    db: Session = Depends(get_database),
    current_user: str = Depends(get_current_user)
):
    """
    Create a new channel.
    
    Args:
        channel_data: Channel creation data
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Created channel
    """
    # Check if channel with username already exists
    existing_channel = db.query(Channel).filter(Channel.username == channel_data.username).first()
    if existing_channel:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Channel with username '{channel_data.username}' already exists"
        )
    
    # Create new channel
    channel = Channel(
        name=channel_data.name,
        username=channel_data.username,
        description=channel_data.description,
        is_active=channel_data.is_active,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc)
    )
    
    db.add(channel)
    db.commit()
    db.refresh(channel)
    
    logger.info(f"Created channel: {channel.name} ({channel.username})")
    return channel

@router.get("/{channel_id}", response_model=ChannelResponse)
def get_channel(
    channel_id: int,
    db: Session = Depends(get_database),
    current_user: str = Depends(get_current_user)
):
    """
    Get a specific channel by ID.
    
    Args:
        channel_id: Channel ID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Channel details
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )
    
    return channel

@router.put("/{channel_id}", response_model=ChannelResponse)
def update_channel(
    channel_id: int,
    channel_data: ChannelUpdate,
    db: Session = Depends(get_database),
    current_user: str = Depends(get_current_user)
):
    """
    Update a channel.
    
    Args:
        channel_id: Channel ID
        channel_data: Channel update data
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Updated channel
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )
    
    # Update fields if provided
    if channel_data.name is not None:
        channel.name = channel_data.name
    if channel_data.description is not None:
        channel.description = channel_data.description
    if channel_data.is_active is not None:
        channel.is_active = channel_data.is_active
    
    channel.updated_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(channel)
    
    logger.info(f"Updated channel: {channel.name} ({channel.username})")
    return channel

@router.delete("/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(
    channel_id: int,
    db: Session = Depends(get_database),
    current_user: str = Depends(get_current_user)
):
    """
    Delete a channel.
    
    Args:
        channel_id: Channel ID
        db: Database session
        current_user: Authenticated user
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )
    
    db.delete(channel)
    db.commit()
    
    logger.info(f"Deleted channel: {channel.name} ({channel.username})")

@router.post("/{channel_id}/ingest", status_code=status.HTTP_202_ACCEPTED)
def trigger_channel_ingestion(
    channel_id: int,
    db: Session = Depends(get_database),
    current_user: str = Depends(get_current_user)
):
    """
    Trigger immediate ingestion for a specific channel.
    
    Args:
        channel_id: Channel ID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Task information
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )
    
    # Trigger ingestion task
    task = ingest_single_channel.delay(channel_id)
    
    logger.info(f"Triggered ingestion for channel: {channel.name}")
    return {
        "message": f"Ingestion triggered for channel '{channel.name}'",
        "task_id": task.id
    }

@router.get("/{channel_id}/stats", response_model=ChannelStats)
def get_channel_stats(
    channel_id: int,
    db: Session = Depends(get_database),
    current_user: str = Depends(get_current_user)
):
    """
    Get statistics for a specific channel.
    
    Args:
        channel_id: Channel ID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Channel statistics
    """
    channel = db.query(Channel).filter(Channel.id == channel_id).first()
    if not channel:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Channel with ID {channel_id} not found"
        )
    
    # Get post statistics
    total_posts = db.query(Post).filter(Post.channel_id == channel_id).count()
    
    # Posts in last 24 hours
    from datetime import timedelta
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    posts_last_24h = db.query(Post).filter(
        Post.channel_id == channel_id,
        Post.created_at >= yesterday
    ).count()
    
    # Last post date
    last_post = db.query(Post).filter(
        Post.channel_id == channel_id
    ).order_by(desc(Post.created_at)).first()
    
    return ChannelStats(
        channel_id=channel_id,
        channel_name=channel.name,
        total_posts=total_posts,
        posts_last_24h=posts_last_24h,
        last_post_date=last_post.created_at if last_post else None
    )
