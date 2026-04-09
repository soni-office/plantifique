from datetime import datetime, timezone
from google.cloud.firestore import FieldFilter
from app.db.firestore import db


class AgentVersionRepository:
    """Tracks active AI agent prompt versions for auditability."""

    def __init__(self):
        self.col = db.collection("agent_versions")

    def get_active(self) -> dict | None:
        docs = self.col.where(filter=FieldFilter("is_active", "==", True)).limit(1).stream()
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        return None

    def create(self, version_id: str, prompt: str, settings: dict) -> dict:
        now = datetime.now(timezone.utc)
        data = {
            "prompt": prompt,
            "settings": settings,
            "is_active": True,
            "created_at": now,
            "model_name": "gemini-2.5-flash",
        }
        self.col.document(version_id).set(data)
        data["id"] = version_id
        return data
