"""
FastAPI routes for legacy community features (votes, comments, feed, referrals).

Auth and profile routes live in community.auth_routes and stay always-on.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc, or_
from sqlalchemy.orm import Session

from core import get_db, settings
from monetization.referrals import get_referral_summary
from monetization.schemas import ReferralSummary
from patches.models import Patch
from racks.models import Rack

from .auth import require_auth
from .models import Comment, User, Vote
from .schemas import (
    CommentCreate,
    CommentResponse,
    CommentUpdate,
    FeedItem,
    FeedResponse,
    VoteCreate,
    VoteResponse,
)

router = APIRouter()


@router.get("/users/me/referrals", response_model=ReferralSummary)
def get_referrals(current_user: User = Depends(require_auth), db: Session = Depends(get_db)):
    """Get referral summary for the current user."""
    if not settings.enable_legacy_referrals:
        raise HTTPException(status_code=404, detail="Referrals are not enabled")
    summary = get_referral_summary(db, user=current_user)
    return ReferralSummary(
        referral_code=summary["referral_code"],
        referral_link=summary["referral_link"],
        earned_credits=summary["earned_credits"],
        pending_referrals=summary["pending_referrals"],
        rewarded_referrals=summary["rewarded_referrals"],
    )


# Vote routes
@router.post("/votes", response_model=VoteResponse, status_code=201)
def create_vote(
    vote: VoteCreate, current_user: User = Depends(require_auth), db: Session = Depends(get_db)
):
    """Create a vote (like) on a rack or patch."""
    # Validate that exactly one target is specified
    if not ((vote.rack_id is None) ^ (vote.patch_id is None)):
        raise HTTPException(
            status_code=400, detail="Must specify either rack_id or patch_id, not both"
        )

    # Check if already voted
    existing = (
        db.query(Vote)
        .filter(
            Vote.user_id == current_user.id,
            or_(Vote.rack_id == vote.rack_id, Vote.patch_id == vote.patch_id),
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Already voted")

    # Create vote
    db_vote = Vote(user_id=current_user.id, rack_id=vote.rack_id, patch_id=vote.patch_id)
    db.add(db_vote)
    db.commit()
    db.refresh(db_vote)

    return db_vote


@router.delete("/votes/{vote_id}", status_code=204)
def delete_vote(
    vote_id: int, current_user: User = Depends(require_auth), db: Session = Depends(get_db)
):
    """Delete a vote."""
    vote = db.query(Vote).filter(Vote.id == vote_id, Vote.user_id == current_user.id).first()
    if not vote:
        raise HTTPException(status_code=404, detail="Vote not found")

    db.delete(vote)
    db.commit()
    return None


# Comment routes
@router.post("/comments", response_model=CommentResponse, status_code=201)
def create_comment(
    comment: CommentCreate,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Create a comment on a rack or patch."""
    # Validate that exactly one target is specified
    if not ((comment.rack_id is None) ^ (comment.patch_id is None)):
        raise HTTPException(
            status_code=400, detail="Must specify either rack_id or patch_id, not both"
        )

    db_comment = Comment(
        user_id=current_user.id,
        rack_id=comment.rack_id,
        patch_id=comment.patch_id,
        content=comment.content,
    )
    db.add(db_comment)
    db.commit()
    db.refresh(db_comment)

    # Attach user
    db_comment.user = current_user

    return db_comment


@router.get("/comments", response_model=list[CommentResponse])
def list_comments(
    rack_id: Optional[int] = None,
    patch_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List comments."""
    query = db.query(Comment)

    if rack_id is not None:
        query = query.filter(Comment.rack_id == rack_id)
    if patch_id is not None:
        query = query.filter(Comment.patch_id == patch_id)

    comments = query.order_by(desc(Comment.created_at)).offset(skip).limit(limit).all()

    # Attach users
    for comment in comments:
        comment.user = db.query(User).filter(User.id == comment.user_id).first()

    return comments


@router.patch("/comments/{comment_id}", response_model=CommentResponse)
def update_comment(
    comment_id: int,
    comment_update: CommentUpdate,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Update a comment."""
    db_comment = (
        db.query(Comment)
        .filter(Comment.id == comment_id, Comment.user_id == current_user.id)
        .first()
    )
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    db_comment.content = comment_update.content
    db.commit()
    db.refresh(db_comment)

    db_comment.user = current_user

    return db_comment


@router.delete("/comments/{comment_id}", status_code=204)
def delete_comment(
    comment_id: int, current_user: User = Depends(require_auth), db: Session = Depends(get_db)
):
    """Delete a comment."""
    db_comment = (
        db.query(Comment)
        .filter(Comment.id == comment_id, Comment.user_id == current_user.id)
        .first()
    )
    if not db_comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    db.delete(db_comment)
    db.commit()
    return None


# Feed route
@router.get("/feed", response_model=FeedResponse)
def get_feed(
    skip: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)
):
    """Get public feed of shared racks and patches."""
    # Get public racks
    racks = (
        db.query(Rack)
        .filter(Rack.is_public.is_(True), Rack.deleted_at.is_(None))
        .order_by(desc(Rack.created_at))
        .all()
    )

    # Get public patches
    patches = (
        db.query(Patch).filter(Patch.is_public.is_(True)).order_by(desc(Patch.created_at)).all()
    )

    # Build feed items
    feed_items: list[FeedItem] = []

    for rack in racks:
        user = db.query(User).filter(User.id == rack.user_id).first()
        vote_count = db.query(Vote).filter(Vote.rack_id == rack.id).count()

        feed_items.append(
            FeedItem(
                type="rack",
                id=rack.id,
                name=rack.name,
                description=rack.description,
                user=user,
                vote_count=vote_count,
                created_at=rack.created_at,
            )
        )

    for patch in patches:
        rack = db.query(Rack).filter(Rack.id == patch.rack_id).first()
        if not rack or rack.deleted_at is not None:
            continue

        user = db.query(User).filter(User.id == rack.user_id).first()
        vote_count = db.query(Vote).filter(Vote.patch_id == patch.id).count()

        feed_items.append(
            FeedItem(
                type="patch",
                id=patch.id,
                name=patch.name,
                description=patch.description,
                user=user,
                vote_count=vote_count,
                created_at=patch.created_at,
            )
        )

    # Sort by created_at
    feed_items.sort(key=lambda x: x.created_at, reverse=True)

    # Paginate
    total = len(feed_items)
    feed_items = feed_items[skip : skip + limit]

    return FeedResponse(total=total, items=feed_items)
