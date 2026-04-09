from datetime import datetime, timedelta, timezone
from google.cloud.firestore import FieldFilter
from google.cloud.firestore_v1 import Query
from app.db.firestore import db


class SampleAnalysisRepository:

    VALID_REVIEW_STATUSES = {"PENDING_REVIEW", "APPROVED", "REJECTED"}

    def __init__(self):
        self.col = db.collection("sample_analyses")

    def get(self, sample_id: str) -> dict | None:
        doc = self.col.document(sample_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        return data

    def get_pending_for_org(self, org_id: str) -> list[dict]:
        docs = (
            self.col
            .where(filter=FieldFilter("org_id", "==", org_id))
            .where(filter=FieldFilter("analysis_status", "==", "QUEUED"))
            .stream()
        )
        return [{**doc.to_dict(), "id": doc.id} for doc in docs]

    def get_review_status(self, sample_id: str) -> str:
        record = self.get(sample_id)
        return record.get("review_status", "PENDING_REVIEW") if record else "PENDING_REVIEW"

    def get_feedback(self, sample_id: str) -> dict:
        record = self.get(sample_id)
        if not record:
            return {"rating": None, "comment": ""}
        return {
            "rating": record.get("feedback_rating"),
            "comment": record.get("feedback_comment", ""),
        }

    def upsert_from_tiktok(self, org_id: str, application: dict) -> bool:
        """
        Upsert a raw TikTok sample application into Firestore.
        - If the document is NEW → sets analysis_status=QUEUED, review_status=PENDING_REVIEW, first_seen_at=now
        - If it already EXISTS → only updates TikTok fields + last_synced_at (never overwrites analysis data)
        Returns True if this was a new record.
        """
        sample_id = application["id"]
        now = datetime.now(timezone.utc)

        tiktok_fields = {
            "org_id": org_id,
            "tiktok_sample_id": sample_id,
            "tiktok_status": application.get("status"),
            "commission_rate": application.get("commission_rate"),
            "available_quantity": application.get("available_quantity"),
            "is_approvable": application.get("is_approvable"),
            "approve_expiration_time": application.get("approve_expiration_time"),
            "order_id": application.get("order_id"),
            "creator": application.get("creator", {}),
            "product": application.get("product", {}),
            "last_synced_at": now,
        }

        doc_ref = self.col.document(sample_id)
        existing = doc_ref.get()

        if not existing.exists:
            tiktok_fields.update({
                "analysis_status": "QUEUED",
                "review_status": "PENDING_REVIEW",
                "first_seen_at": now,
            })
            doc_ref.set(tiktok_fields)
            return True

        doc_ref.update(tiktok_fields)
        return False

    def list_for_org(
        self,
        org_id: str,
        page_size: int = 30,
        start_after_id: str | None = None,
    ) -> tuple[list[dict], str | None]:
        """
        Cursor-based paginated list for an org, newest first.
        Returns (items, next_cursor) — next_cursor is None on the last page.

        NOTE: Requires a Firestore composite index on (org_id ASC, first_seen_at DESC).
        If you get an index error, follow the link in the error message to create it.
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

    def get_all_tiktok_pending_ids(self, org_id: str) -> set[str]:
        """
        Return the set of document IDs in this org that still have tiktok_status=PENDING.
        Uses a field-mask select so only one field is read per document — cheap even at 2 000 docs.
        Filters in Python to avoid needing a composite index on (org_id, tiktok_status).
        """
        docs = (
            self.col
            .where(filter=FieldFilter("org_id", "==", org_id))
            .select(["tiktok_status"])
            .stream()
        )
        return {doc.id for doc in docs if doc.to_dict().get("tiktok_status") == "PENDING"}

    def mark_processed_on_shop(self, sample_ids: set[str], ttl_days: int = 1) -> int:
        """
        Mark a set of sample IDs as no longer PENDING on TikTok Shop.
        Sets:
          tiktok_status  = PROCESSED_ON_SHOP
          delete_at      = now + ttl_days  ← Firestore TTL field auto-deletes the doc
        Uses batched writes (≤500 per batch, Firestore limit).
        Returns the count of documents updated.
        """
        if not sample_ids:
            return 0

        now = datetime.now(timezone.utc)
        delete_at = now + timedelta(days=ttl_days)
        ids = list(sample_ids)
        updated = 0

        for i in range(0, len(ids), 500):
            batch = db.batch()
            for sid in ids[i : i + 500]:
                batch.update(self.col.document(sid), {
                    "tiktok_status": "PROCESSED_ON_SHOP",
                    "processed_on_shop_at": now,
                    "delete_at": delete_at,
                    "updated_at": now,
                })
                updated += 1
            batch.commit()

        return updated

    def queue(self, sample_id: str, org_id: str) -> dict:
        now = datetime.now(timezone.utc)
        data = {
            "org_id": org_id,
            "tiktok_sample_id": sample_id,
            "analysis_status": "QUEUED",
            "review_status": "PENDING_REVIEW",
            "created_at": now,
            "updated_at": now,
        }
        self.col.document(sample_id).set(data, merge=True)
        data["id"] = sample_id
        return data

    def save_analysis_result(self, sample_id: str, org_id: str, result: dict) -> None:
        now = datetime.now(timezone.utc)
        self.col.document(sample_id).set({
            "org_id": org_id,
            "tiktok_sample_id": sample_id,
            "analysis_status": "COMPLETED",
            "analysis_score": result.get("llm_score"),
            "analysis_reasoning": result.get("llm_reasoning"),
            "final_decision": result.get("final_decision"),
            "tier": result.get("tier"),
            "filters_passed": result.get("filters_passed"),
            "validation_reason": result.get("validation_reason"),
            "review_status": "PENDING_REVIEW",
            "processed_at": now,
            "updated_at": now,
        }, merge=True)

    def mark_failed(self, sample_id: str, error: str) -> None:
        self.col.document(sample_id).set({
            "analysis_status": "FAILED",
            "error_message": error,
            "updated_at": datetime.now(timezone.utc),
        }, merge=True)

    def set_review_status(self, sample_id: str, status: str) -> None:
        if status not in self.VALID_REVIEW_STATUSES:
            raise ValueError(
                f"Invalid review_status '{status}'. Must be one of: {self.VALID_REVIEW_STATUSES}"
            )
        self.col.document(sample_id).set({
            "review_status": status,
            "updated_at": datetime.now(timezone.utc),
        }, merge=True)

    def set_feedback(self, sample_id: str, rating: str, comment: str = "") -> dict:
        if rating not in ("up", "down"):
            raise ValueError("Feedback rating must be 'up' or 'down'")
        now = datetime.now(timezone.utc)
        self.col.document(sample_id).set({
            "feedback_rating": rating,
            "feedback_comment": comment,
            "updated_at": now,
        }, merge=True)
        return {"rating": rating, "comment": comment}
