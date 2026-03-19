from datetime import datetime, timezone
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
            .where("org_id", "==", org_id)
            .where("analysis_status", "==", "QUEUED")
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
