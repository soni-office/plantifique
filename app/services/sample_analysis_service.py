"""
Business logic for sample analyses.

Owns: cache → DB reads, TikTok sync, agent evaluation, review + feedback writes.
The API layer calls only this service; raw repo/cache imports stay here.
"""
import logging
from typing import Optional

from app.cache import cache, keys, ttl
from app.repository.sample_analysis_repository import SampleAnalysisRepository
from app.services.token_service import TokenService
from app.clients.tiktok.sample_client import TikTokSampleClient
from app.utils.shop_ciphers import shop_cipher
from app.models import SampleAnalysis

logger = logging.getLogger(__name__)

_VALID_REVIEW_STATUSES = {"PENDING_REVIEW", "APPROVED", "REJECTED"}


class SampleAnalysisService:

    def __init__(self):
        self.repo = SampleAnalysisRepository()
        self.token_service = TokenService()

    # ── Auth helpers ──────────────────────────────────────────────────────

    def _get_token_and_cipher(self, org_id: str) -> tuple[str, str]:
        access_token = self.token_service.get_valid_access_token(org_id)
        res = shop_cipher(org_id)
        cipher = res["data"]["shops"][0]["cipher"]
        return access_token, cipher

    # ── List ──────────────────────────────────────────────────────────────

    def list(self, org_id: str, page_size: int = 30, cursor: Optional[str] = None) -> dict:
        """Cache-first paginated list for an org."""
        def _fetch():
            items, next_cursor = self.repo.list_for_org(
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

    # ── Sync ──────────────────────────────────────────────────────────────

    def sync(self, org_id: str, user_id: str) -> dict:
        """
        Pull all PENDING sample requests from TikTok and upsert into Firestore.
        Invalidates the full org sample list cache on completion.
        """
        logger.info("Sync started org=%s by=%s", org_id, user_id)
        access_token, cipher = self._get_token_and_cipher(org_id)

        page_token: Optional[str] = None
        new_count = 0
        updated_count = 0
        page_num = 0
        tiktok_ids_seen: set[str] = set()

        # Forward pass: upsert everything TikTok says is PENDING
        while True:
            page_num += 1
            result = TikTokSampleClient.search(
                access_token=access_token,
                shop_cipher=cipher,
                page_size=50,
                page_token=page_token,
                status="PENDING",
            )

            if result.get("code") != 0:
                logger.error("TikTok API error during sync: %s", result)
                raise RuntimeError(f"TikTok API error: {result.get('message')}")

            batch = result.get("data", {}).get("sample_applications") or []
            for app in batch:
                if app['status'] != "PENDING":
                    logger.warning("Skipping non-PENDING sample_id=%s status=%s", app["id"], app["status"])
                    continue
                tiktok_ids_seen.add(app["id"])
                is_new = self.repo.upsert_from_tiktok(org_id=org_id, application=app)
                if is_new:
                    new_count += 1
                else:
                    updated_count += 1

            logger.info(
                "Sync page=%s batch=%s new=%s updated=%s",
                page_num, len(batch), new_count, updated_count,
            )
            next_token = result.get("data", {}).get("next_page_token", "")
            if not next_token or not batch:
                break
            page_token = next_token

        # Backward pass: mark anything no longer PENDING on TikTok
        db_pending_ids = self.repo.get_all_tiktok_pending_ids(org_id)
        stale_ids = db_pending_ids - tiktok_ids_seen
        processed_count = self.repo.mark_processed_on_shop(stale_ids, ttl_days=1)

        # Invalidate entire sample list cache for this org
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

    # ── Evaluate ──────────────────────────────────────────────────────────

    def evaluate(self, org_id: str, sample_id: str, user_id: str, threshold: int = 70) -> dict:
        """
        Trigger AI analysis for a sample.
        Skips if analysis_score already exists. Invalidates item + list cache on success.
        """
        from app.agents.sample_analyzer.runner import run_sr_agent

        existing = self.repo.get(sample_id)
        if existing and existing.get("analysis_status") == "COMPLETED":
            logger.warning(
                "sample_id=%s already analysed, skipping re-evaluation", sample_id
            )
            return {"status": "skipped", "message": "Analysis already exists for this sample_id", "data": SampleAnalysis.from_dict(existing).get_analysis_result()}

        logger.info(
            "Evaluating sample_id=%s org=%s by=%s", sample_id, org_id, user_id
        )
        access_token, cipher = self._get_token_and_cipher(org_id)
        self.repo.mark_queued(sample_id=sample_id, org_id=org_id)

        result = run_sr_agent(
            sample_request_id=sample_id,
            access_token=access_token,
            shop_cipher=cipher,
            threshold=threshold,
        )
        self.repo.save_analysis_result(
            sample_id=sample_id,
            org_id=org_id,
            result=result,
        )
        cache.invalidate(keys.sample_item(org_id, sample_id))
        cache.invalidate_prefix(keys.sample_list_prefix(org_id))
        logger.info("Evaluation complete sample_id=%s", sample_id)

        # Normalize to DB field names so the frontend always gets the same shape
        normalized = {
            "sample_request_id": result.get("sample_request_id"),
            "final_decision": result.get("final_decision"),
            "tier": result.get("tier"),
            "filters_passed": result.get("filters_passed"),
            "validation_reason": result.get("validation_reason"),
            "analysis_score": result.get("llm_score"),
            "analysis_reasoning": result.get("llm_reasoning"),
            "decision_reason": result.get("decision_reason"),
            "rich_creator_detail": result.get("rich_creator_detail"),
            "rich_product_detail": result.get("rich_product_detail"),
        }
        return {"status": "success", "data": normalized}

    # ── Review status ─────────────────────────────────────────────────────

    def update_review_status(self, org_id: str, sample_id: str, status: str) -> dict:
        """Validate and persist a human review decision; invalidates item cache."""
        if status not in _VALID_REVIEW_STATUSES:
            raise ValueError(
                f"Invalid review_status '{status}'. Must be one of: {_VALID_REVIEW_STATUSES}"
            )
        self.repo.set_review_status(sample_id, status)
        cache.invalidate(keys.sample_item(org_id, sample_id))
        return {"status": "success", "sample_id": sample_id, "review_status": status}

    # ── Feedback ──────────────────────────────────────────────────────────

    def submit_feedback(
        self, org_id: str, sample_id: str, rating: str, comment: str = ""
    ) -> dict:
        """Validate and persist thumbs up/down feedback; invalidates item cache."""
        if rating not in ("up", "down"):
            raise ValueError("Feedback rating must be 'up' or 'down'")
        self.repo.set_feedback(sample_id, rating, comment)
        cache.invalidate(keys.sample_item(org_id, sample_id))
        return {
            "status": "success",
            "sample_id": sample_id,
            "feedback": {"rating": rating, "comment": comment},
        }

    # ── Review state (cached) ─────────────────────────────────────────────

    def get_review_state(self, org_id: str, sample_id: str) -> dict:
        """Cache-first fetch of review status + feedback for a sample."""
        def _fetch():
            doc = self.repo.get(sample_id)
            if not doc:
                return {
                    "sample_id": sample_id,
                    "review_status": None,
                    "feedback": {"rating": None, "comment": ""},
                }
            return {
                "sample_id": sample_id,
                "review_status": doc.get("review_status"),
                "feedback": {
                    "rating": doc.get("feedback_rating"),
                    "comment": doc.get("feedback_comment", ""),
                },
            }

        return cache.cache_or_fetch(
            keys.sample_item(org_id, sample_id),
            ttl.SAMPLE_ITEM,
            _fetch,
        )
