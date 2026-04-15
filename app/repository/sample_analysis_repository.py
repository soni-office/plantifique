"""
Raw Firestore I/O for the `sample_analyses` collection.

Rules:
  - Every write goes through SampleAnalysis.to_dict() so DB structure is enforced by the model.
  - Reads return plain dicts (with "id" set to the doc ID).
  - No business logic, no cache, no TikTok API calls here.
"""
from datetime import datetime, timedelta, timezone

from google.cloud.firestore import FieldFilter
from google.cloud.firestore_v1 import Query

from app.db.firestore import db
from app.models import SampleAnalysis


class SampleAnalysisRepository:

    VALID_REVIEW_STATUSES = {"PENDING_REVIEW", "APPROVED", "REJECTED"}

    def __init__(self):
        self.col = db.collection("sample_analyses")

    # ── Single-document reads ─────────────────────────────────────────────

    def get(self, sample_id: str) -> dict | None:
        """Return the doc as a plain dict, or None if it does not exist."""
        doc = self.col.document(sample_id).get()
        if not doc.exists:
            return None
        return {**doc.to_dict(), "id": doc.id}

    # ── Org-scoped list ───────────────────────────────────────────────────

    def list_for_org(
        self,
        org_id: str,
        page_size: int = 30,
        start_after_id: str | None = None,
    ) -> tuple[list[dict], str | None]:
        """
        Cursor-based paginated list, newest first.
        Returns (items, next_cursor) — next_cursor is None on the last page.

        Requires a Firestore composite index: (org_id ASC, first_seen_at DESC).
        The link to create it will appear in the error message if it is missing.
        """
        query = (
            self.col
            .where(filter=FieldFilter("org_id", "==", org_id))
            .order_by("first_seen_at", direction=Query.DESCENDING)
            .limit(page_size + 1)
        )

        if start_after_id:
            snap = self.col.document(start_after_id).get()
            if snap.exists:
                query = query.start_after(snap)

        docs = list(query.stream())
        has_more = len(docs) > page_size
        if has_more:
            docs = docs[:page_size]

        items = [{**doc.to_dict(), "id": doc.id} for doc in docs]
        next_cursor = docs[-1].id if has_more else None
        return items, next_cursor

    # def get_queued_for_org(self, org_id: str) -> list[dict]:
    #     """Return all docs with analysis_status=QUEUED (in-flight / automation jobs)."""
    #     docs = (
    #         self.col
    #         .where(filter=FieldFilter("org_id", "==", org_id))
    #         .where(filter=FieldFilter("analysis_status", "==", "QUEUED"))
    #         .stream()
    #     )
    #     return [{**doc.to_dict(), "id": doc.id} for doc in docs]

    def get_all_tiktok_pending_ids(self, org_id: str) -> set[str]:
        """
        Return doc IDs that still have tiktok_status=PENDING.
        Uses a field-mask projection — cheap even at 2 000 docs.
        """
        docs = (
            self.col
            .where(filter=FieldFilter("org_id", "==", org_id))
            .select(["tiktok_status"])
            .stream()
        )
        return {doc.id for doc in docs if doc.to_dict().get("tiktok_status") == "PENDING"}

    # ── Writes (all via SampleAnalysis.to_dict()) ─────────────────────────

    def upsert_from_tiktok(self, org_id: str, application: dict) -> bool:
        """
        Upsert a raw TikTok sample application payload.
        - NEW doc  → full SampleAnalysis model written (analysis_status=NOT_STARTED)
        - EXISTING → only TikTok-sourced fields updated; analysis data is never overwritten
        Returns True if this was a new record.
        """
        sample_id = application["id"]
        now = datetime.now(timezone.utc)
        doc_ref = self.col.document(sample_id)
        existing = doc_ref.get()

        if not existing.exists:
            model = SampleAnalysis(
                id=sample_id,
                org_id=org_id,
                tiktok_sample_id=sample_id,
                tiktok_status=application.get("status", "PENDING"),
                commission_rate=application.get("commission_rate"),
                available_quantity=application.get("available_quantity"),
                is_approvable=application.get("is_approvable"),
                approve_expiration_time=application.get("approve_expiration_time"),
                order_id=application.get("order_id"),
                creator=application.get("creator") or {},
                product=application.get("product") or {},
                last_synced_at=now,
                analysis_status="NOT_STARTED",
                review_status="PENDING_REVIEW",
                first_seen_at=now,
                updated_at=now,
            )
            doc_ref.set(model.to_dict())
            return True

        # Partial update — only TikTok-sourced fields
        doc_ref.update({
            "tiktok_status": application.get("status", "PENDING"),
            "commission_rate": application.get("commission_rate"),
            "available_quantity": application.get("available_quantity"),
            "is_approvable": application.get("is_approvable"),
            "approve_expiration_time": application.get("approve_expiration_time"),
            "order_id": application.get("order_id"),
            "creator": application.get("creator") or {},
            "product": application.get("product") or {},
            "last_synced_at": now,
        })
        return False

    def mark_queued(self, sample_id: str, org_id: str) -> None:
        """Set analysis_status=QUEUED when a user triggers evaluation."""
        self.col.document(sample_id).set(
            {"analysis_status": "QUEUED", "updated_at": datetime.now(timezone.utc)},
            merge=True,
        )

    def save_analysis_result(self, sample_id: str, org_id: str, result: dict) -> None:
        """Persist agent output. Merges into existing doc via model field names."""
        now = datetime.now(timezone.utc)
        # Build a partial SampleAnalysis and write only the analysis fields
        update = {
            "org_id": org_id,
            "tiktok_sample_id": sample_id,
            "analysis_status": "COMPLETED",
            "commerce_score": result.get("commerce_score"),
            "commerce_reasoning": result.get("commerce_reasoning"),
            "aesthetic_score": result.get("aesthetic_score"),
            "aesthetic_reasoning": result.get("aesthetic_reasoning"),
            "top_3_video_urls": result.get("top_3_video_urls") or [],
            "visual_score": result.get("visual_score"),
            "visual_reasoning": result.get("visual_reasoning"),
            "compatibility_status": result.get("compatibility_status"),
            "final_decision": result.get("final_decision"),
            "tier": result.get("tier"),
            "filters_passed": result.get("filters_passed"),
            "validation_reason": result.get("validation_reason"),
            "decision_reason": result.get("decision_reason"),
            "review_status": "PENDING_REVIEW",
            "processed_at": now,
            "updated_at": now,
        }
        self.col.document(sample_id).set(update, merge=True)



    def mark_failed(self, sample_id: str, error: str) -> None:
        self.col.document(sample_id).set(
            {
                "analysis_status": "FAILED",
                "error_message": error,
                "updated_at": datetime.now(timezone.utc),
            },
            merge=True,
        )

    def set_review_status(self, sample_id: str, status: str) -> None:
        if status not in self.VALID_REVIEW_STATUSES:
            raise ValueError(
                f"Invalid review_status '{status}'. Must be one of: {self.VALID_REVIEW_STATUSES}"
            )
        self.col.document(sample_id).set(
            {"review_status": status, "updated_at": datetime.now(timezone.utc)},
            merge=True,
        )

    def set_feedback(self, sample_id: str, rating: str, comment: str = "") -> None:
        if rating not in ("up", "down"):
            raise ValueError("Feedback rating must be 'up' or 'down'")
        self.col.document(sample_id).set(
            {
                "feedback_rating": rating,
                "feedback_comment": comment,
                "updated_at": datetime.now(timezone.utc),
            },
            merge=True,
        )
        return {"rating": rating, "comment": comment}

    def mark_processed_on_shop(self, sample_ids: set[str], ttl_days: int = 1) -> int:
        """
        Mark stale IDs as PROCESSED_ON_SHOP and schedule TTL deletion.
        Uses batched writes (≤500 per Firestore limit).
        """
        if not sample_ids:
            return 0

        now = datetime.now(timezone.utc)
        delete_at = now + timedelta(days=ttl_days)
        ids = list(sample_ids)
        updated = 0

        for i in range(0, len(ids), 500):
            batch = db.batch()
            for sid in ids[i: i + 500]:
                batch.update(self.col.document(sid), {
                    "tiktok_status": "PROCESSED_ON_SHOP",
                    "processed_on_shop_at": now,
                    "delete_at": delete_at,
                    "updated_at": now,
                })
                updated += 1
            batch.commit()

        return updated
