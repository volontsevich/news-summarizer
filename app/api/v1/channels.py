"""Channel management API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import crud as channel_crud, crud as post_crud
from app.db.models import Channel, Post

router = APIRouter()


@router.get("/", response_model=List[dict])
async def list_channels(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """List all channels."""
    channels = db.query(Channel).offset(skip).limit(limit).all()
    return [
        {
            "id": str(ch.id),
            "username": ch.username,
            "name": ch.name,
            "description": ch.description,
            "is_active": ch.is_active,
            "created_at": ch.created_at.isoformat(),
            "updated_at": ch.updated_at.isoformat()
        }
        for ch in channels
    ]


@router.post("/")
async def create_channel(
    username: str = Query(..., description="Channel username"),
    name: str = Query(..., description="Channel name"),
    description: str = Query(None, description="Channel description"),
    db: Session = Depends(get_db)
):
    """Create a new channel."""
    try:
        channel = Channel(
            username=username,
            name=name,
            description=description,
            is_active=True
        )
        
        db.add(channel)
        db.commit()
        db.refresh(channel)
        
        return {
            "id": str(channel.id),
            "username": channel.username,
            "name": channel.name,
            "description": channel.description,
            "url": f"https://t.me/{channel.username}",
            "created_at": channel.created_at.isoformat(),
            "updated_at": channel.updated_at.isoformat(),
            "message": "Channel created successfully!"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create channel: {str(e)}")


@router.get("/{channel_id}")
async def get_channel(
    channel_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific channel by ID."""
    try:
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        
        return {
        "id": str(channel.id),
        "username": channel.username,
        "name": channel.name,
        "description": channel.description,
        "is_active": channel.is_active,
        "created_at": channel.created_at.isoformat(),
        "updated_at": channel.updated_at.isoformat()
    }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving channel: {str(e)}")


@router.get("/{channel_id}/posts")
async def get_channel_posts(
    channel_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Get posts from a specific channel."""
    try:
        # Verify channel exists
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        
        # Get posts for this channel
        posts = db.query(Post).filter(Post.channel_id == channel_id).offset(skip).limit(limit).all()
        
        return [
            {
                "id": str(post.id),
                "message_id": post.message_id,
                "text": post.raw_text[:500] + "..." if len(post.raw_text) > 500 else post.raw_text,
                "language": post.language,
                "created_at": post.created_at.isoformat(),
                "has_summary": bool(post.processed)
            }
            for post in posts
        ]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving posts: {str(e)}")


@router.get("/{channel_id}/stats")
async def get_channel_stats(
    channel_id: str,
    db: Session = Depends(get_db)
):
    """Get channel statistics."""
    try:
        channel = db.query(Channel).filter(Channel.id == channel_id).first()
        if not channel:
            raise HTTPException(status_code=404, detail="Channel not found")
        
        # Get post count
        total_posts = db.query(Post).filter(Post.channel_id == channel_id).count()
        
        # Get recent activity (posts in last 24 hours)
        from datetime import datetime, timedelta
        recent_cutoff = datetime.utcnow() - timedelta(days=1)
        recent_posts = db.query(Post).filter(
            Post.channel_id == channel_id,
            Post.created_at >= recent_cutoff
        ).count()
        
        return {
        "channel_id": channel_id,
        "channel_name": channel.name,
        "total_posts": total_posts,
        "recent_posts_24h": recent_posts,
        "is_active": channel.is_active,
        "created_at": channel.created_at.isoformat(),
        "last_post_at": channel.updated_at.isoformat()
    }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving stats: {str(e)}")
