import logging

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from app.api.auth_session import get_current_user
from app.services.sample_analysis_service import SampleAnalysisService

router = APIRouter(prefix="/tiktok/samples", tags=["TikTok Sample Requests"])
logger = logging.getLogger(__name__)


# ── List ──────────────────────────────────────────────────────────────────

@router.get("")
async def list_sample_requests(
    page_size: int = Query(30, ge=1, le=100),
    cursor: str | None = Query(None, description="Cursor from previous page's next_cursor"),
    user=Depends(get_current_user),
):
    """Return a cached page of sample requests from Firestore."""
    return SampleAnalysisService().list(
        org_id=user["org_id"],
        page_size=page_size,
        cursor=cursor,
    )


# ── Sync ──────────────────────────────────────────────────────────────────

@router.post("/sync")
async def sync_sample_requests(user=Depends(get_current_user)):
    """Pull PENDING sample requests from TikTok and upsert into Firestore."""
    try:
        return SampleAnalysisService().sync(
            org_id=user["org_id"],
            user_id=user["id"],
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Evaluate ──────────────────────────────────────────────────────────────

@router.post("/{sample_id}/evaluate")
async def evaluate_sample_request(
    sample_id: str,
    threshold: int = Query(70, description="Minimum score required to accept"),
    user=Depends(get_current_user),
):
    """Manually trigger AI analysis for a sample (Phase 1 → 2 → 3 → decision)."""
    try:
        return SampleAnalysisService().evaluate(
            org_id=user["org_id"],
            sample_id=sample_id,
            user_id=user["id"],
            threshold=threshold,
        )
    except Exception as e:
        logger.error("Error evaluating sample_id=%s: %s", sample_id, e)
        raise HTTPException(status_code=500, detail=str(e))


# ── Review status ─────────────────────────────────────────────────────────

class ReviewStatusBody(BaseModel):
    status: str


@router.patch("/{sample_id}/review-status")
async def update_review_status(
    sample_id: str,
    body: ReviewStatusBody,
    user=Depends(get_current_user),
):
    """Update the human review decision for a sample."""
    try:
        return SampleAnalysisService().update_review_status(
            org_id=user["org_id"],
            sample_id=sample_id,
            status=body.status,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ── Feedback ──────────────────────────────────────────────────────────────

class FeedbackBody(BaseModel):
    rating: str
    comment: str = ""


@router.post("/{sample_id}/feedback")
async def submit_feedback(
    sample_id: str,
    body: FeedbackBody,
    user=Depends(get_current_user),
):
    """Submit thumbs up/down feedback for an AI analysis."""
    try:
        return SampleAnalysisService().submit_feedback(
            org_id=user["org_id"],
            sample_id=sample_id,
            rating=body.rating,
            comment=body.comment,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ── Review state ──────────────────────────────────────────────────────────

@router.get("/{sample_id}/review")
async def get_review_state(
    sample_id: str,
    user=Depends(get_current_user),
):
    """Fetch the current review status and feedback for a sample. Cached per item."""
    return SampleAnalysisService().get_review_state(
        org_id=user["org_id"],
        sample_id=sample_id,
    )
