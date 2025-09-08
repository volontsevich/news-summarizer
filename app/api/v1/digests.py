"""Digest management API endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db import crud as digest_crud
from app.db.models import Digest

router = APIRouter()


@router.get("/", response_model=List[dict])
async def list_digests(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db)
):
    """List all digests."""
    digests = db.query(Digest).offset(skip).limit(limit).all()
    
    return [
        {
            "id": str(digest.id),
            "title": digest.title,
            "summary": digest.summary[:200] + "..." if len(digest.summary) > 200 else digest.summary,
            "created_at": digest.created_at.isoformat(),
            "sent_at": digest.sent_at.isoformat() if digest.sent_at else None,
            "status": "sent" if digest.sent_at else "pending"
        }
        for digest in digests
    ]


@router.post("/generate")
async def generate_digest(
    title: str = Query(..., description="Digest title"),
    hours: int = Query(24, description="Hours of content to include"),
    max_posts: int = Query(10, description="Maximum number of posts to include"),
    db: Session = Depends(get_db)
):
    """Generate a new digest from recent posts."""
    try:
        from datetime import datetime, timedelta
        from app.db.models import Post
        
        # Calculate timeframe
        timeframe_end = datetime.utcnow()
        timeframe_start = timeframe_end - timedelta(hours=hours)
        
        # Get recent posts
        recent_posts = db.query(Post).filter(
            Post.created_at >= timeframe_start
        ).order_by(Post.created_at.desc()).limit(max_posts).all()
        
        if not recent_posts:
            raise HTTPException(status_code=404, detail="No recent posts found for digest")
        
        # Create digest summary
        summary_parts = []
        for post in recent_posts:
            if post.processed and hasattr(post.processed, 'summary_md'):
                summary_parts.append(f"• {post.processed.summary_md}")
            else:
                text_preview = post.raw_text[:100] + "..." if len(post.raw_text) > 100 else post.raw_text
                summary_parts.append(f"• {text_preview}")
        
        digest_summary = "\n".join(summary_parts)
        
        # Determine most common language
        languages = [post.language for post in recent_posts if post.language]
        most_common_language = max(set(languages), key=languages.count) if languages else "en"
        
        # Create digest
        digest = Digest(
            timeframe_start=timeframe_start,
            timeframe_end=timeframe_end,
            language=most_common_language,
            summary_md=digest_summary
        )
        
        db.add(digest)
        db.commit()
        db.refresh(digest)
        
        return {
            "id": str(digest.id),
            "timeframe_start": digest.timeframe_start.isoformat(),
            "timeframe_end": digest.timeframe_end.isoformat(),
            "language": digest.language,
            "summary": digest.summary_md,
            "post_count": len(recent_posts),
            "created_at": digest.created_at.isoformat(),
            "message": "Digest generated successfully!"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to generate digest: {str(e)}")


@router.get("/{digest_id}")
async def get_digest(
    digest_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific digest by ID."""
    digest = db.query(Digest).filter(Digest.id == digest_id).first()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")
    
    return {
        "id": str(digest.id),
        "timeframe_start": digest.timeframe_start.isoformat(),
        "timeframe_end": digest.timeframe_end.isoformat(),
        "language": digest.language,
        "summary": digest.summary_md,
        "created_at": digest.created_at.isoformat()
    }


@router.post("/{digest_id}/send")
async def send_digest(
    digest_id: str,
    recipients: str = Query(..., description="Comma-separated email addresses"),
    db: Session = Depends(get_db)
):
    """Send a digest to specified recipients."""
    digest = db.query(Digest).filter(Digest.id == digest_id).first()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")
    
    try:
        from datetime import datetime
        
        # Parse recipients
        recipient_list = [email.strip() for email in recipients.split(',')]
        
        # Here you would typically send the actual email
        # For now, just mark as sent
        digest.sent_at = datetime.utcnow()
        db.commit()
        
        return {
            "message": "Digest sent successfully",
            "digest_id": digest_id,
            "digest_title": digest.title,
            "recipients": recipient_list,
            "sent_at": digest.sent_at.isoformat(),
            "note": "Email sending functionality to be implemented"
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to send digest: {str(e)}")


@router.delete("/{digest_id}")
async def delete_digest(
    digest_id: str,
    db: Session = Depends(get_db)
):
    """Delete a digest."""
    digest = db.query(Digest).filter(Digest.id == digest_id).first()
    if not digest:
        raise HTTPException(status_code=404, detail="Digest not found")
    
    try:
        db.delete(digest)
        db.commit()
        return {"message": "Digest deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete digest: {str(e)}")


@router.get("/stats/")
async def get_digest_stats(
    db: Session = Depends(get_db)
):
    """Get digest statistics."""
    try:
        total_digests = db.query(Digest).count()
        sent_digests = db.query(Digest).filter(Digest.sent_at.isnot(None)).count()
        
        # Get recent digests (in last 7 days)
        from datetime import datetime, timedelta
        recent_cutoff = datetime.utcnow() - timedelta(days=7)
        recent_digests = db.query(Digest).filter(
            Digest.created_at >= recent_cutoff
        ).count()
        
        return {
            "total_digests": total_digests,
            "sent_digests": sent_digests,
            "pending_digests": total_digests - sent_digests,
            "recent_digests_7d": recent_digests,
            "send_rate": (sent_digests / total_digests * 100) if total_digests > 0 else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving stats: {str(e)}")
