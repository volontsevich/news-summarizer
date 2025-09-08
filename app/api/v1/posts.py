"""Post management API endpoints."""

from typing import List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.db import crud as post_crud
from app.db.models import Post

router = APIRouter()


@router.get("/", response_model=List[dict])
async def list_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    channel_id: Optional[str] = Query(None),
    language: Optional[str] = Query(None),
    has_summary: Optional[bool] = Query(None),
    db: Session = Depends(get_db)
):
    """List posts with optional filtering."""
    query = db.query(Post)
    
    if channel_id:
        query = query.filter(Post.channel_id == channel_id)
    if language:
        query = query.filter(Post.language == language)
    if has_summary is not None:
        if has_summary:
            query = query.filter(Post.summary.isnot(None))
        else:
            query = query.filter(Post.summary.is_(None))
    
    posts = query.offset(skip).limit(limit).all()
    
    return [
        {
            "id": str(post.id),
            "message_id": post.message_id,
            "text": post.raw_text[:200] + "..." if len(post.raw_text) > 200 else post.raw_text,
            "language": post.language,
            "channel_id": str(post.channel_id),
            "created_at": post.created_at.isoformat(),
            "has_summary": bool(post.processed and hasattr(post.processed, 'summary_md'))
        }
        for post in posts
    ]


@router.get("/{post_id}")
async def get_post(
    post_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific post by ID."""
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    return {
        "id": str(post.id),
        "message_id": post.message_id,
        "text": post.raw_text,
        "language": post.language,
        "channel_id": str(post.channel_id),
        "summary": getattr(post.processed, 'summary_md', None) if post.processed else None,
        "created_at": post.created_at.isoformat(),
        "updated_at": post.updated_at.isoformat()
    }


@router.get("/search/")
async def search_posts(
    q: str = Query(..., description="Search query"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """Search posts by text content."""
    try:
        posts = db.query(Post).filter(
            Post.raw_text.contains(q)
        ).offset(skip).limit(limit).all()
        
        return [
            {
                "id": str(post.id),
                "message_id": post.message_id,
                "text": post.raw_text[:300] + "..." if len(post.raw_text) > 300 else post.raw_text,
                "language": post.language,
                "channel_id": str(post.channel_id),
                "created_at": post.created_at.isoformat(),
                "relevance_score": 1.0  # Simplified score
            }
            for post in posts
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/stats/")
async def get_posts_stats(
    db: Session = Depends(get_db)
):
    """Get posts statistics."""
    try:
        total_posts = db.query(Post).count()
        
        # Get language distribution
        language_stats = db.query(
            Post.language, 
            func.count(Post.id).label('count')
        ).group_by(Post.language).all()
        
        # Get posts with summaries (through processed relationship)
        posts_with_summaries = db.query(Post).join(Post.processed).count()
        
        return {
            "total_posts": total_posts,
            "posts_with_summaries": posts_with_summaries,
            "language_distribution": {
                lang: count for lang, count in language_stats
            },
            "summary_coverage": (posts_with_summaries / total_posts * 100) if total_posts > 0 else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving stats: {str(e)}")
