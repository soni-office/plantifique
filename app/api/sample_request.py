from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
import logging

from app.api.auth_session import get_current_user
from app.services.tiktok.token_service import TokenService
from app.services.tiktok.sample_service import TikTokSampleService
from app.repository.sample_analysis_repository import SampleAnalysisRepository
from app.repository.creator_repository import CreatorRepository
from app.repository.product_repository import ProductRepository
from app.utils.shop_ciphers import shop_cipher
from app.core.config import settings

router = APIRouter(prefix="/tiktok/samples", tags=["TikTok Sample Requests"])

logger = logging.getLogger(__name__)


@router.get("/search")
async def search_sample_requests(
    page_size: int = Query(20),
    user=Depends(get_current_user),
):
    """Fetch sample requests for this org. Returns mock data when MOCK_TIKTOK=true."""
    logger.info("Searching sample requests for user=%s org=%s", user["id"], user["org_id"])

    if settings.mock_sample_requests:
        from app.mock.sample_mock_data import get_mock_sample_requests
        return get_mock_sample_requests()

    token_service = TokenService()
    access_token = token_service.get_valid_access_token(user["org_id"])
    res = shop_cipher(user["org_id"])
    cipher = res["data"]["shops"][0]["cipher"]

    return TikTokSampleService.search(
        access_token=access_token,
        shop_cipher=cipher,
        page_size=page_size,
    )


@router.post("/{sample_id}/evaluate")
async def evaluate_sample_request(
    sample_id: str,
    threshold: int = Query(70, description="Minimum score required to accept"),
    user=Depends(get_current_user),
):
    """Manually trigger AI analysis for a sample. Saves result to Firestore."""
    from app.agents.sample_analyzer.runner import run_sr_agent

    logger.info("Evaluating sample_id=%s for user=%s org=%s", sample_id, user["id"], user["org_id"])

    analysis_repo = SampleAnalysisRepository()

    try:
        if settings.mock_tiktok:
            access_token = "mock_access_token"
            cipher = "mock_cipher"
        else:
            token_service = TokenService()
            access_token = token_service.get_valid_access_token(user["org_id"])
            res = shop_cipher(user["org_id"])
            cipher = res["data"]["shops"][0]["cipher"]

        result = run_sr_agent(
            sample_request_id=sample_id,
            access_token=access_token,
            shop_cipher=cipher,
            threshold=threshold,
        )

        analysis_repo.save_analysis_result(
            sample_id=sample_id,
            org_id=user["org_id"],
            result=result,
        )

        creator_repo = CreatorRepository()
        product_repo = ProductRepository()

        if result.get("rich_creator_detail"):
            creator_id = (
                result["rich_creator_detail"].get("creator_id")
                or result["rich_creator_detail"].get("id")
            )
            if creator_id:
                creator_repo.upsert(creator_id=creator_id, org_id=user["org_id"], data=result["rich_creator_detail"])

        if result.get("rich_product_detail") and result["rich_product_detail"].get("id"):
            product_repo.upsert(
                product_id=result["rich_product_detail"]["id"],
                org_id=user["org_id"],
                data=result["rich_product_detail"],
            )

        return {"status": "success", "data": result}

    except Exception as e:
        logger.error("Error evaluating sample_id=%s: %s", sample_id, e)
        analysis_repo.mark_failed(sample_id=sample_id, error=str(e))
        return {"status": "error", "message": str(e)}


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
        repo = SampleAnalysisRepository()
        repo.set_review_status(sample_id, body.status)
        logger.info("Review status updated: sample_id=%s status=%s by user=%s", sample_id, body.status, user["id"])
        return {"status": "success", "sample_id": sample_id, "review_status": body.status}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


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
        repo = SampleAnalysisRepository()
        record = repo.set_feedback(sample_id, body.rating, body.comment)
        return {"status": "success", "sample_id": sample_id, "feedback": record}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{sample_id}/review")
async def get_review_state(
    sample_id: str,
    user=Depends(get_current_user),
):
    """Fetch the current review status and feedback for a sample."""
    repo = SampleAnalysisRepository()
    return {
        "sample_id": sample_id,
        "review_status": repo.get_review_status(sample_id),
        "feedback": repo.get_feedback(sample_id),
    }