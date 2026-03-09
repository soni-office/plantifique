from datetime import datetime, timezone
from google.cloud import firestore
from app.db.firestore import db


class UserRepository:

    def __init__(self):
        self.col = db.collection("users")

    def get_by_tiktok_open_id(self, open_id: str) -> dict | None:
        """Find a user by their TikTok open_id."""
        docs = self.col.where("tiktok_open_id", "==", open_id).limit(1).stream()
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id  # attach Firestore doc ID as 'id'
            return data
        return None

    def get_by_id(self, user_id: str) -> dict | None:
        """Find a user by their Firestore document ID."""
        doc = self.col.document(user_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        return None

    def create(self, open_id: str, username: str | None = None) -> dict:
        """Create a new user document and return it."""
        now = datetime.now(timezone.utc)
        data = {
            "tiktok_open_id": open_id,
            "username": username,
            "email": None,
            "created_at": now,
            "updated_at": now,
        }
        _, doc_ref = self.col.add(data)
        data["id"] = doc_ref.id
        return data