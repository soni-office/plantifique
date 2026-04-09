import logging

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel

from app.api.auth_session import get_current_user
from app.services.tiktok.token_service import TokenService
from app.services.tiktok.sample_service import TikTokSampleService
from app.repository.sample_analysis_repository import SampleAnalysisRepository
from app.repository.creator_repository import CreatorRepository
from app.repository.product_repository import ProductRepository
from app.utils.shop_ciphers import shop_cipher
from app.cache import cache, keys, ttl

router = APIRouter(prefix="/tiktok/samples", tags=["TikTok Sample Requests"])
logger = logging.getLogger(__name__)


def _get_token_and_cipher(org_id: str) -> tuple[str, str]:
    access_token = TokenService().get_valid_access_token(org_id)
    res = shop_cipher(org_id)
    cipher = res["data"]["shops"][0]["cipher"]
    return access_token, cipher


# ── List (from DB, paginated + cached) ───────────────────────────────────

@router.get("")
async def list_sample_requests(
    page_size: int = Query(30, ge=1, le=100),
    cursor: str | None = Query(None, description="Cursor from previous page's next_cursor"),
    user=Depends(get_current_user),
):
    """
    Return a page of sample requests from Firestore (previously synced from TikTok).
    Results are cached per (org, page_size, cursor). The entire org's sample cache
    is wiped on every successful sync so the list is always fresh after a sync.
    """
    org_id = user["org_id"]

    def _fetch():
        repo = SampleAnalysisRepository()
        items, next_cursor = repo.list_for_org(
            org_id=org_id,
            page_size=page_size,
            start_after_id=cursor or None,
        )
        return {
            "items": items,
            "next_cursor": next_cursor,
            "has_more": next_cursor is not None,
        }

    return cache.cache_or_fetch(
        keys.sample_list(org_id, page_size, cursor),
        ttl.SAMPLE_LIST,
        _fetch,
    )


# ── Sync from TikTok into DB ──────────────────────────────────────────────

@router.post("/sync")
async def sync_sample_requests(
    user=Depends(get_current_user),
):
    """
    Pull all PENDING sample requests from TikTok and upsert them into Firestore.
    Safe to re-run — existing analysis data is never overwritten.
    On completion, invalidates the entire org's sample list cache so the next
    GET immediately reflects the updated DB state.
    """
    org_id = user["org_id"]
    logger.info("Sync started org=%s by=%s", org_id, user["id"])
    access_token, cipher = _get_token_and_cipher(org_id)

    repo = SampleAnalysisRepository()
    page_token: str | None = None
    new_count = 0
    updated_count = 0
    page_num = 0
    tiktok_ids_seen: set[str] = set()

    # ── Forward pass: upsert everything TikTok says is PENDING ───────────
    while True:
        page_num += 1
        result = TikTokSampleService.search(
            access_token=access_token,
            shop_cipher=cipher,
            page_size=50,
            page_token=page_token,
            status="PENDING",
        )

        if result.get("code") != 0:
            logger.error("TikTok API error during sync: %s", result)
            raise HTTPException(status_code=502, detail=f"TikTok API error: {result.get('message')}")

        batch = result.get("data", {}).get("sample_applications") or []
        for app in batch:
            tiktok_ids_seen.add(app["id"])
            is_new = repo.upsert_from_tiktok(org_id=org_id, application=app)
            if is_new:
                new_count += 1
            else:
                updated_count += 1

        logger.info("Sync page=%s batch=%s new=%s updated=%s", page_num, len(batch), new_count, updated_count)

        next_token = result.get("data", {}).get("next_page_token", "")
        if not next_token or not batch:
            break
        page_token = next_token

    # ── Backward pass: mark anything no longer PENDING on TikTok ─────────
    db_pending_ids = repo.get_all_tiktok_pending_ids(org_id)
    stale_ids = db_pending_ids - tiktok_ids_seen
    processed_count = repo.mark_processed_on_shop(stale_ids, ttl_days=1)

    # ── Invalidate the entire sample list cache for this org ──────────────
    # All paginated pages are wiped so the next GET is served fresh from DB.
    removed = cache.invalidate_prefix(keys.sample_list_prefix(org_id))
    logger.info(
        "Sync complete org=%s new=%s updated=%s processed=%s pages=%s cache_evicted=%s",
        org_id, new_count, updated_count, processed_count, page_num, removed,
    )
    return {
        "status": "ok",
        "new": new_count,
        "updated": updated_count,
        "marked_processed": processed_count,
        "pages_fetched": page_num,
    }


# ── AI Evaluate ───────────────────────────────────────────────────────────

@router.post("/{sample_id}/evaluate")
async def evaluate_sample_request(
    sample_id: str,
    threshold: int = Query(70, description="Minimum score required to accept"),
    user=Depends(get_current_user),
):
    """Manually trigger AI analysis for a sample. Saves result to Firestore."""
    from app.agents.sample_analyzer.runner import run_sr_agent

    org_id = user["org_id"]
    logger.info("Evaluating sample_id=%s for user=%s org=%s", sample_id, user["id"], org_id)

    analysis_repo = SampleAnalysisRepository()

    try:
        access_token, cipher = _get_token_and_cipher(org_id)
        result = run_sr_agent(
            sample_request_id=sample_id,
            access_token=access_token,
            shop_cipher=cipher,
            threshold=threshold,
        )

        analysis_repo.save_analysis_result(
            sample_id=sample_id,
            org_id=org_id,
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
                creator_repo.upsert(creator_id=creator_id, org_id=org_id, data=result["rich_creator_detail"])

        if result.get("rich_product_detail") and result["rich_product_detail"].get("id"):
            product_repo.upsert(
                product_id=result["rich_product_detail"]["id"],
                org_id=org_id,
                data=result["rich_product_detail"],
            )

        # Invalidate cached item state and the list so analysis results appear immediately
        cache.invalidate(
            keys.sample_item(org_id, sample_id),
        )
        cache.invalidate_prefix(keys.sample_list_prefix(org_id))

        return {"status": "success", "data": result}

    except Exception as e:
        logger.error("Error evaluating sample_id=%s: %s", sample_id, e)
        analysis_repo.mark_failed(sample_id=sample_id, error=str(e))
        return {"status": "error", "message": str(e)}


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
        repo = SampleAnalysisRepository()
        repo.set_review_status(sample_id, body.status)
        # Invalidate item cache so the updated status is visible immediately
        cache.invalidate(keys.sample_item(user["org_id"], sample_id))
        logger.info("Review status updated sample_id=%s status=%s by=%s", sample_id, body.status, user["id"])
        return {"status": "success", "sample_id": sample_id, "review_status": body.status}
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
        repo = SampleAnalysisRepository()
        record = repo.set_feedback(sample_id, body.rating, body.comment)
        # Invalidate so feedback shows up immediately on next fetch
        cache.invalidate(keys.sample_item(user["org_id"], sample_id))
        return {"status": "success", "sample_id": sample_id, "feedback": record}
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{sample_id}/review")
async def get_review_state(
    sample_id: str,
    user=Depends(get_current_user),
):
    """Fetch the current review status and feedback for a sample. Cached per item."""
    org_id = user["org_id"]

    def _fetch():
        repo = SampleAnalysisRepository()
        return {
            "sample_id": sample_id,
            "review_status": repo.get_review_status(sample_id),
            "feedback": repo.get_feedback(sample_id),
        }

    return cache.cache_or_fetch(
        keys.sample_item(org_id, sample_id),
        ttl.SAMPLE_ITEM,
        _fetch,
    )
