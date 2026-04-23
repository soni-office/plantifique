import logging
from fastapi import APIRouter, Header, HTTPException
from app.core.config import settings
from app.services.automation_service import AutomationService

router = APIRouter(prefix="/internal", tags=["Internal"])

logger = logging.getLogger(__name__)


def _verify_internal_secret(x_internal_secret: str) -> None:
    """
    Verify the request comes from Google Cloud Scheduler, not a random caller.
    The secret is stored in GCP Secret Manager / env var INTERNAL_API_SECRET.
    Returns None on success, raises HTTP 401 on failure.
    """
    if not settings.internal_api_secret:
        logger.warning(
            "INTERNAL_API_SECRET not configured — internal endpoint is unsecured!"
        )
        return  # Allow in dev if secret not set — warn loudly

    if x_internal_secret != settings.internal_api_secret:
        logger.warning("Unauthorized internal endpoint access attempt")
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: invalid internal secret",
        )


@router.post("/process-samples")
async def trigger_sample_processing(
    x_internal_secret: str = Header(..., description="Secret shared with Cloud Scheduler"),
):
    """
    Endpoint called by Google Cloud Scheduler every hour.
    Validates the shared secret, then kicks off the AutomationService synchronously.
    
    Cloud Run prevents background tasks from running after HTTP response unless "CPU Always On" is paid for.
    Since we only run exactly 3 creators (taking ~3-4 minutes), doing it synchronously easily safely stays
    under the 10-minute Request Timeout limit without freezing the AI!
    """
    _verify_internal_secret(x_internal_secret)

    try:
        service = AutomationService(org_id=settings.org_id)
        # Runs SYNCHRONOUSLY — Cloud Run keeps the request alive until done.
        # Batch limit comes from BATCH_PROCESS_SAMPLE_REQUESTS_LIMIT env var (default 5).
        summary = await service.process_pending()
        
        logger.info(
            "[Scheduler] Processing complete: processed=%d skipped=%d failed=%d",
            summary.get("processed", 0),
            summary.get("skipped", 0),
            summary.get("failed", 0),
        )
        return {
            "status": "success",
            "message": "Sequential processing completed safely",
            "summary": summary,
            "org_id": settings.org_id,
        }
    except Exception as e:
        logger.error("[Scheduler] AutomationService failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def internal_health(
    x_internal_secret: str = Header(...),
):
    """
    Lightweight health check for the internal scheduler.
    Can be used to verify the secret is configured correctly.
    """
    _verify_internal_secret(x_internal_secret)
    return {"status": "ok", "org_id": settings.org_id}
