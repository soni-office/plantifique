from datetime import datetime, timezone
from app.db.firestore import db


class CreatorRepository:
    """Caches TikTok Creator profiles by creator_id (document ID)."""

    def __init__(self):
        self.col = db.collection("creators")

    def get(self, creator_id: str) -> dict | None:
        doc = self.col.document(creator_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        return data

    def upsert(self, creator_id: str, org_id: str, data: dict) -> dict:
        now = datetime.now(timezone.utc)
        data.update({"org_id": org_id, "last_synced_at": now, "updated_at": now})
        self.col.document(creator_id).set(data, merge=True)
        data["id"] = creator_id
        return data

    def get_by_org(self, org_id: str) -> list[dict]:
        docs = self.col.where("org_id", "==", org_id).stream()
        return [{**doc.to_dict(), "id": doc.id} for doc in docs]
