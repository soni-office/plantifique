from datetime import datetime, timezone
from google.cloud import firestore
from app.db.firestore import db


class TikTokTokenRepository:

    def __init__(self):
        self.col = db.collection("tiktok_tokens")

    def get_by_user_id(self, user_id: str) -> dict | None:
        """Find a token record by user_id."""
        docs = self.col.where("user_id", "==", user_id).limit(1).stream()
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        return None

    def create(self, user_id: str) -> dict:
        """Create a blank token record for a user."""
        now = datetime.now(timezone.utc)
        data = {
            "user_id": user_id,
            "access_token": "",
            "refresh_token": None,
            "scope": None,
            "access_token_expire_in": 0,
            "refresh_token_expire_in": None,
            "updated_at": now,
        }
        _, doc_ref = self.col.add(data)
        data["id"] = doc_ref.id
        return data

    def update(self, doc_id: str, fields: dict) -> None:
        """Update specific fields on a token document."""
        fields["updated_at"] = datetime.now(timezone.utc)
        self.col.document(doc_id).update(fields)