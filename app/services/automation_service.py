import asyncio
import logging
from app.services.token_service import TokenService
from app.clients.tiktok.sample_client import TikTokSampleClient
from app.repository.sample_analysis_repository import SampleAnalysisRepository
from app.repository.user_repository import UserRepository
from app.utils.shop_ciphers import shop_cipher
from app.agents.sample_analyzer.runner import run_sr_agent

logger = logging.getLogger(__name__)

_MAX_CONCURRENT = 3


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
        self.user_repo = UserRepository()

    async def process_pending(self) -> dict:
        """Main entry point — returns { processed, skipped, failed } summary."""
        logger.info("[AutomationService] Starting for org_id=%s", self.org_id)

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
            samples = tiktok_response.get("data", {}).get("sample_requests", [])
            if not samples:
                return {"processed": 0, "skipped": 0, "failed": 0}
        except Exception as e:
            logger.error("[AutomationService] TikTok fetch failed: %s", e)
            return {"processed": 0, "skipped": 0, "failed": 0, "error": str(e)}

        to_process, skipped = [], 0
        for sample in samples:
            sample_id = sample.get("id") or sample.get("sample_id")
            if not sample_id:
                continue
            existing = self.analysis_repo.get(sample_id)
            if existing and existing.get("analysis_status") in ("COMPLETED", "QUEUED"):
                skipped += 1
                continue
            self.analysis_repo.mark_queued(sample_id=sample_id, org_id=self.org_id)
            to_process.append(sample_id)

        if not to_process:
            return {"processed": 0, "skipped": skipped, "failed": 0}

        semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
        results = await asyncio.gather(
            *[self._process_one(sid, access_token, cipher, semaphore) for sid in to_process],
            return_exceptions=True,
        )

        processed = sum(1 for r in results if r is True)
        failed = len(results) - processed
        logger.info("[AutomationService] Done — processed=%d skipped=%d failed=%d", processed, skipped, failed)
        return {"processed": processed, "skipped": skipped, "failed": failed}

    async def _process_one(self, sample_id: str, access_token: str, cipher: str, semaphore: asyncio.Semaphore) -> bool:
        async with semaphore:
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
                self.analysis_repo.mark_failed(sample_id=sample_id, error=str(e))
                return False

    async def _resolve_shop_cipher(self) -> str | None:
        try:
            users = self.user_repo.get_all_by_org(self.org_id)
            admin = next((u for u in users if u.get("role") == "ORG_ADMIN"), None)
            if not admin:
                return None
            res = shop_cipher(admin["id"])
            return res["data"]["shops"][0]["cipher"]
        except Exception as e:
            logger.error("[AutomationService] shop_cipher error: %s", e)
            return None
