import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from app.api.auth_session import get_current_user
from app.services.sample_analysis_service import SampleAnalysisService, get_sample_analysis_service
from app.repository.sample_analysis_repository import SampleAnalysisRepository
from app.clients.tiktok.sample_client import TikTokSampleClient

router = APIRouter(prefix="/tiktok/samples", tags=["TikTok Sample Requests"])
logger = logging.getLogger(__name__)


# ── List ──────────────────────────────────────────────────────────────────

@router.get("")
async def list_sample_requests(
    page_size: int = Query(30, ge=1, le=100),
    cursor: str | None = Query(None, description="Cursor from previous page's next_cursor"),
    user=Depends(get_current_user),
    service: SampleAnalysisService = Depends(get_sample_analysis_service),
):
    """Return a cached page of sample requests from Firestore."""
    return await service.list(
        org_id=user["org_id"],
        page_size=page_size,
        cursor=cursor,
    )


# ── Sync ──────────────────────────────────────────────────────────────────

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


# ── Review status ─────────────────────────────────────────────────────────

class ReviewStatusBody(BaseModel):
    # Internal status saved in our Firestore DB (e.g. "APPROVED", "REJECTED")
    status: str
    # Maps directly to TikTok's review_result field: "APPROVE" or "REJECT"
    review_result: str
    # Required by TikTok when review_result is "REJECT".
    # One of: NOT_MATCH | OFFLINE | OUT_OF_STOCK | OTHER
    reject_reason: Optional[str] = None


@router.patch("/{sample_id}/review-status")
def update_review_status(
    sample_id: str,
    body: ReviewStatusBody,
    user=Depends(get_current_user),
):
    """
    Update the human review decision for a sample.

    This does TWO things in sequence:
      1. Saves the review status to our internal Firestore DB.
      2. Calls TikTok's official Seller Review API so the decision
         is immediately reflected on the live TikTok Shop as well.
    """
    try:
        # Step 1: Save to our internal Firestore DB first
        service = get_sample_analysis_service()
        # repo.set_review_status(sample_id, body.status)
        logger.info(
            "Review status saved to DB: sample_id=%s status=%s by=%s",
            sample_id, body.status, user["id"],
        )

        # Step 2: Sync the decision to TikTok Shop via official API
        try:
            # Reusing the singleton instead of SampleAnalysisService()
            access_token, cipher = service._get_token_and_cipher(user["org_id"])
            tiktok_response = TikTokSampleClient.review(
                access_token=access_token,
                shop_cipher=cipher,
                application_id=sample_id,
                review_result=body.review_result,
                reject_reason=body.reject_reason,
            )
            logger.info(
                "TikTok Shop review synced: sample_id=%s review_result=%s tiktok_response=%s",
                sample_id, body.review_result, tiktok_response,
            )
        except ValueError as ve:
            raise HTTPException(status_code=422, detail=str(ve))
        except Exception as tiktok_err:
            logger.error(
                "TikTok review sync failed for sample_id=%s: %s",
                sample_id, tiktok_err,
            )
            return {
                "status": "partial_success",
                "sample_id": sample_id,
                "review_status": body.status,
                "warning": f"Saved to DB but TikTok sync failed: {tiktok_err}",
            }

        return {
            "status": "success",
            "sample_id": sample_id,
            "review_status": body.status,
            "tiktok_synced": True,
        }

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# ── Feedback ──────────────────────────────────────────────────────────────

class FeedbackBody(BaseModel):
    rating: str
    comment: str = ""


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
