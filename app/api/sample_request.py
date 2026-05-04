import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from app.cache import cache, keys

from app.api.auth_session import get_current_user
from app.services.sample_analysis_service import SampleAnalysisService, get_sample_analysis_service
from app.repository.sample_analysis_repository import SampleAnalysisRepository
from app.schemas.sample_request import ReviewStatusBody, FeedbackBody

router = APIRouter(prefix="/tiktok/samples", tags=["TikTok Sample Requests"])
logger = logging.getLogger(__name__)

_ALLOWED_FILTER_FIELDS = {"review_status", "analysis_status", "tiktok_status", "creator_username", "sample_id"}


# ── List ──────────────────────────────────────────────────────────────────

@router.get("")
async def list_sample_requests(
    page_size: int = Query(30, ge=1, le=100),
    cursor: str | None = Query(None, description="Cursor from previous page's next_cursor"),
    filter_field: str | None = Query(None, description="Field to filter on"),
    filter_value: str | None = Query(None, description="Exact value to match"),
    user=Depends(get_current_user),
    service: SampleAnalysisService = Depends(get_sample_analysis_service),
):
    """Return a cached page of sample requests. Optionally filter by a single field."""
    
    if filter_field or filter_value:
        if not filter_field or not filter_value:
            raise HTTPException(
                status_code=422,
                detail="Both filter_field and filter_value must be provided together",
            )
        if filter_field not in _ALLOWED_FILTER_FIELDS:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid filter_field '{filter_field}'. Allowed: {sorted(_ALLOWED_FILTER_FIELDS)}",
            )
        return await service.list_filtered(
            org_id=user["org_id"],
            filter_field=filter_field,
            filter_value=filter_value,
            page_size=page_size,
            cursor=cursor,
        )
    return await service.list(
        org_id=user["org_id"],
        page_size=page_size,
        cursor=cursor,
    )


# ── Sync ─────────────────────────────────────────────────────────────────

@router.post("/sync")
def sync_sample_requests(
    user=Depends(get_current_user),
    service: SampleAnalysisService = Depends(get_sample_analysis_service),
):
    """Pull PENDING sample requests from TikTok and upsert into Firestore."""
    try:
        return service.sync(
            org_id=user["org_id"],
            user_id=user["id"],
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


# ── Evaluate ──────────────────────────────────────────────────────────────

@router.post("/{sample_id}/evaluate")
def evaluate_sample_request(
    sample_id: str,
    threshold: int = Query(70, description="Minimum score required to accept"),
    user=Depends(get_current_user),
    service: SampleAnalysisService = Depends(get_sample_analysis_service),
):
    """Manually trigger AI analysis for a sample (Phase 1 → 2 → 3 → decision)."""
    try:
        return service.evaluate(
            org_id=user["org_id"],
            sample_id=sample_id,
            user_id=user["id"],
            threshold=threshold,
        )
    except Exception as e:
        logger.error("Error evaluating sample_id=%s: %s", sample_id, e)
        raise HTTPException(status_code=500, detail=str(e))



@router.patch("/{sample_id}/review-status")
def update_review_status(
    sample_id: str,
    body: ReviewStatusBody,
    user=Depends(get_current_user),
    service: SampleAnalysisService = Depends(get_sample_analysis_service),
):
    """
    Update the human review decision for a sample.

    1. Validates the status value.
    2. Hits TikTok's Seller Review API — only on success do we write to DB.
    3. Persists the review status to Firestore and invalidates the list cache.
    """
    # Validate before touching any external system
    if body.status not in {"PENDING_REVIEW", "APPROVED", "REJECTED"}:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid review_status '{body.status}'. Must be one of: PENDING_REVIEW, APPROVED, REJECTED",
        )

    # Step 1: Sync to TikTok first — if this fails, DB stays untouched
    try:
        service.update_review_status(
            org_id=user["org_id"],
            sample_id=sample_id,
            internal_status=body.status,
            review_result=body.review_result,
            reject_reason=body.reject_reason,
            user_id=user["id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Review status update failed for sample_id=%s: %s", sample_id, e)
        raise HTTPException(status_code=500, detail=str(e))

    logger.info(
        "Review status successfully updated for sample_id=%s to status=%s by user_id=%s",
        sample_id, body.status, user["id"]
    )
    return {
        "status": "success",
        "sample_id": sample_id,
        "review_status": body.status,
        "tiktok_synced": True,
    }



@router.post("/{sample_id}/feedback")
def submit_feedback(
    sample_id: str,
    body: FeedbackBody,
    user=Depends(get_current_user),
    service: SampleAnalysisService = Depends(get_sample_analysis_service),
):
    """Submit thumbs up/down feedback for an AI analysis."""
    try:
        return service.submit_feedback(
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
    service: SampleAnalysisService = Depends(get_sample_analysis_service),
):
    """Fetch the current review status and feedback for a sample. Cached per item."""
    return await service.get_review_state(
        org_id=user["org_id"],
        sample_id=sample_id,
    )
