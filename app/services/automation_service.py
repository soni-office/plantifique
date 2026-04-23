import asyncio
import logging

from app.services.token_service import get_token_service
from app.clients.tiktok.sample_client import TikTokSampleClient
from app.repository.sample_analysis_repository import SampleAnalysisRepository
from app.utils.shop_ciphers import shop_cipher
from app.agents.sample_analyzer.runner import run_sr_agent
from app.cache import cache, keys
from app.core.config import settings

logger = logging.getLogger(__name__)
batch_process_sample_requests_limit = settings.batch_process_sample_requests_limit


class AutomationService:
    """
    Background service that processes sample requests via AI.
    Runs on a schedule (e.g. hourly via Cloud Scheduler).
    Deduplicates using Firestore so failed/new samples are retried.
    """

    def __init__(self, org_id: str, threshold: int = 70):
        self.org_id = org_id
        self.threshold = threshold
        self.token_service = get_token_service()
        self.analysis_repo = SampleAnalysisRepository()

    async def process_pending(self, limit: int = batch_process_sample_requests_limit) -> dict:
        """
        Main entry point — returns { processed, skipped, failed } summary.

        Paginates through TikTok pages until we have `limit` samples to process
        or there are no more pages. This ensures that samples sitting on page 2+
        are not silently skipped when page 1 is fully processed already.
        """
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

        # ── Paginated collection phase ─────────────────────────────────────
        # Walk TikTok pages until we have enough unprocessed samples OR run out of pages.

        to_process: list[str] = []
        retry_counts: dict[str, int] = {}
        skipped = 0
        page_token: str | None = None
        page_num = 0

        while len(to_process) < limit:
            page_num += 1
            try:
                tiktok_response = TikTokSampleClient.search(
                    access_token=access_token,
                    shop_cipher=cipher,
                    page_size=50,
                    page_token=page_token,
                )
            except Exception as e:
                logger.error("[AutomationService] TikTok fetch failed on page %d: %s", page_num, e)
                if page_num == 1:
                    return {"processed": 0, "skipped": 0, "failed": 0, "error": str(e)}
                break  # already collected some from earlier pages — proceed with those

            if tiktok_response.get("code") != 0:
                logger.error("[AutomationService] TikTok API error on page %d: %s", page_num, tiktok_response)
                if page_num == 1:
                    return {"processed": 0, "skipped": 0, "failed": 0, "error": tiktok_response.get("message")}
                break

            data = tiktok_response.get("data", {})
            samples = data.get("sample_applications", [])
            logger.info("[AutomationService] Page %d — %d sample(s) from TikTok", page_num, len(samples))

            if not samples:
                break  # no more records on TikTok

            for sample in samples:
                sample_id = sample.get("id") or sample.get("sample_id")
                if not sample_id:
                    continue

                existing = self.analysis_repo.get(sample_id)

                if existing and existing.get("analysis_status") in ("COMPLETED", "QUEUED", "PERMANENTLY_FAILED"):
                    skipped += 1
                    continue

                retry_count = existing.get("retry_count", 0) if existing else 0
                if retry_count >= 3:
                    self.analysis_repo.mark_permanently_failed(sample_id)
                    skipped += 1
                    continue

                # Reached the batch limit — stop collecting, don't mark these as QUEUED
                if len(to_process) >= limit:
                    break

                # Sync full creator/product data before analysis so agent has everything it needs
                self.analysis_repo.upsert_from_tiktok(org_id=self.org_id, application=sample)
                # TODO: mark QUEUED only right before starting the agent, not here — currently
                #       marking early prevents manual re-evaluation while batch is running.
                self.analysis_repo.mark_queued(sample_id=sample_id, org_id=self.org_id)
                cache.invalidate_prefix(keys.sample_list_prefix(self.org_id))
                to_process.append(sample_id)
                retry_counts[sample_id] = retry_count

            # Stop paginating if we hit the limit or there's no next page
            next_page_token = data.get("next_page_token", "")
            if not next_page_token or len(to_process) >= limit:
                break

            page_token = next_page_token

        if not to_process:
            logger.info("[AutomationService] Nothing to process after %d page(s) — skipped=%d", page_num, skipped)
            return {"processed": 0, "skipped": skipped, "failed": 0}

        # ── Sequential processing phase ────────────────────────────────────

        processed = 0
        failed = 0
        for i, sid in enumerate(to_process):
            logger.info("[AutomationService] Processing job %d of %d: %s", i + 1, len(to_process), sid)
            success = await self._process_one(sid, access_token, cipher, retry_counts[sid])

            if success:
                processed += 1
            else:
                failed += 1

            # Rate-limit gap between jobs (skip after the last one)
            if i < len(to_process) - 1:
                logger.info("[AutomationService] 10-second gap before next job...")
                await asyncio.sleep(10)

        # Force the frontend to refresh the list
        cache.invalidate_prefix(keys.sample_list_prefix(self.org_id))

        logger.info(
            "[AutomationService] Done — processed=%d skipped=%d failed=%d pages_fetched=%d",
            processed, skipped, failed, page_num,
        )
        return {"processed": processed, "skipped": skipped, "failed": failed}

    async def _process_one(self, sample_id: str, access_token: str, cipher: str, current_retry_count: int) -> bool:
        try:
            loop = asyncio.get_running_loop()
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
