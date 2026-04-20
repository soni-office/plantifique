import asyncio
import logging
from app.services.token_service import TokenService
from app.clients.tiktok.sample_client import TikTokSampleClient
from app.repository.sample_analysis_repository import SampleAnalysisRepository
from app.utils.shop_ciphers import shop_cipher
from app.agents.sample_analyzer.runner import run_sr_agent
from app.cache import cache, keys

logger = logging.getLogger(__name__)

class AutomationService:
    """
    Background service that processes sample requests via AI.
    Runs on a schedule (e.g. hourly via Cloud Scheduler).
    Deduplicates using Firestore so failed/new samples are retried.
    """

    def __init__(self, org_id: str, threshold: int = 70):
        self.org_id = org_id
        self.threshold = threshold
        self.token_service = TokenService()
        self.analysis_repo = SampleAnalysisRepository()

    async def process_pending(self, limit: int = 3) -> dict:
        """Main entry point — returns { processed, skipped, failed } summary."""
        logger.info("[AutomationService] Starting for org_id=%s, limit=%d", self.org_id, limit)

        try:
            access_token = self.token_service.get_valid_access_token(self.org_id)
        except ValueError as e:
            logger.error("[AutomationService] Token error for org_id=%s: %s", self.org_id, e)
            return {"processed": 0, "skipped": 0, "failed": 0, "error": str(e)}

        cipher = await self._resolve_shop_cipher()
        if not cipher:
            logger.error("[AutomationService] No shop cipher for org_id=%s", self.org_id)
            return {"processed": 0, "skipped": 0, "failed": 0, "error": "No shop cipher"}

        try:
            tiktok_response = TikTokSampleClient.search(
                access_token=access_token,
                shop_cipher=cipher,
                page_size=50,
            )
            # Check TikTok API returned success (code 0)
            if tiktok_response.get("code") != 0:
                logger.error("[AutomationService] TikTok API error: %s", tiktok_response)
                return {"processed": 0, "skipped": 0, "failed": 0, "error": tiktok_response.get("message")}

            samples = tiktok_response.get("data", {}).get("sample_applications", [])
            if not samples:
                logger.info("[AutomationService] No PENDING sample applications found.")
                return {"processed": 0, "skipped": 0, "failed": 0}
        except Exception as e:
            logger.error("[AutomationService] TikTok fetch failed: %s", e)
            return {"processed": 0, "skipped": 0, "failed": 0, "error": str(e)}

        to_process, skipped = [], 0
        retry_counts = {}
        for sample in samples:
            sample_id = sample.get("id") or sample.get("sample_id")
            if not sample_id:
                continue
            existing = self.analysis_repo.get(sample_id)
            # Skip if already being processed or finished
            if existing and existing.get("analysis_status") in ("COMPLETED", "QUEUED", "PERMANENTLY_FAILED"):
                skipped += 1
                continue
                
            retry_count = existing.get("retry_count", 0) if existing else 0
            if retry_count >= 3:
                self.analysis_repo.mark_permanently_failed(sample_id)
                skipped += 1
                continue
                
            # Limit the batch immediately. Leave the rest alone so they aren't marked as QUEUED!
            if len(to_process) >= limit:
                break
            
            # CRITICAL: Sync full creator data (username, product_id, etc.) BEFORE processing.
            # This prevents the AI from crashing when it tries to look up an empty username in Firestore.
            self.analysis_repo.upsert_from_tiktok(org_id=self.org_id, application=sample)
                
            self.analysis_repo.mark_queued(sample_id=sample_id, org_id=self.org_id)
            to_process.append(sample_id)
            retry_counts[sample_id] = retry_count

        if not to_process:
            return {"processed": 0, "skipped": skipped, "failed": 0}

        processed = 0
        failed = 0
        
        for i, sid in enumerate(to_process):
            logger.info(f"[AutomationService] Processing job {i+1} of {len(to_process)}: {sid}")
            success = await self._process_one(sid, access_token, cipher, retry_counts[sid])
            
            if success:
                processed += 1
            else:
                failed += 1
                
            # Sleep 15 seconds after every payload, EXCEPT for the very last one.
            if i < len(to_process) - 1:
                logger.info("[AutomationService] Taking a 15-second gap to prevent rate limiting...")
                await asyncio.sleep(15)

        # Force the frontend to refresh the list by clearing the cache
        cache.invalidate_prefix(keys.sample_list_prefix(self.org_id))

        logger.info("[AutomationService] Done — processed=%d skipped=%d failed=%d", processed, skipped, failed)
        return {"processed": processed, "skipped": skipped, "failed": failed}

    async def _process_one(self, sample_id: str, access_token: str, cipher: str, current_retry_count: int) -> bool:
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: run_sr_agent(
                    sample_request_id=sample_id,
                    access_token=access_token,
                    shop_cipher=cipher,
                    threshold=self.threshold,
                )
            )
            self.analysis_repo.save_analysis_result(
                sample_id=sample_id, org_id=self.org_id, result=result
            )
            return True
        except Exception as e:
            logger.error("[AutomationService] Failed sample_id=%s: %s", sample_id, e)
            self.analysis_repo.mark_failed(sample_id=sample_id, error=str(e), retry_count=current_retry_count + 1)
            return False

    async def _resolve_shop_cipher(self) -> str | None:
        try:
            res = shop_cipher(self.org_id)
            return res["data"]["shops"][0]["cipher"]
        except Exception as e:
            logger.error("[AutomationService] shop_cipher error: %s", e)
            return None
