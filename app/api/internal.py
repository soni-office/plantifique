import logging
from fastapi import APIRouter, Header, HTTPException, BackgroundTasks
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
    background_tasks: BackgroundTasks,
    x_internal_secret: str = Header(..., description="Secret shared with Cloud Scheduler"),
):
    """
    Endpoint called by Google Cloud Scheduler every hour.
    Validates the shared secret, then kicks off the AutomationService
    as a BACKGROUND task — returns 202 Accepted immediately so the
    Cloud Scheduler doesn't time out waiting for AI calls to finish.

    GCP Cloud Scheduler config:
        Schedule:  0 * * * *   (every hour)
        URL:       https://<backend-url>/internal/process-samples
        Method:    POST
        Header:    X-Internal-Secret: <INTERNAL_API_SECRET value>
    """
    _verify_internal_secret(x_internal_secret)

    async def _run():
        try:
            service = AutomationService(org_id=settings.org_id)
            summary = await service.process_pending()
            logger.info(
                "[Scheduler] Processing complete: processed=%d skipped=%d failed=%d",
                summary.get("processed", 0),
                summary.get("skipped", 0),
                summary.get("failed", 0),
            )
        except Exception as e:
            logger.error("[Scheduler] AutomationService failed: %s", e)

    background_tasks.add_task(_run)

    logger.info(
        "[Scheduler] process-samples triggered for org_id=%s", settings.org_id
    )
    return {
        "status": "accepted",
        "message": "Processing started in background",
        "org_id": settings.org_id,
    }


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
