from datetime import datetime, timezone
from app.db.firestore import db
from app.core.token_crypto import TokenCrypto


class TikTokTokenRepository:

    def __init__(self):
        self.col = db.collection("tiktok_tokens")
        self.crypto = TokenCrypto()

    def get_by_user_id(self, user_id: str) -> dict | None:
        """Find a token record by user_id."""
        docs = self.col.where("user_id", "==", user_id).limit(1).stream()
        for doc in docs:
            data = doc.to_dict()
            data["access_token"] = self.crypto.decrypt(data.get("access_token"))
            data["refresh_token"] = self.crypto.decrypt(data.get("refresh_token"))
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
        if "access_token" in fields:
            fields["access_token"] = self.crypto.encrypt(fields["access_token"])
        if "refresh_token" in fields:
            fields["refresh_token"] = self.crypto.encrypt(fields["refresh_token"])
        fields["updated_at"] = datetime.now(timezone.utc)
        self.col.document(doc_id).update(fields)
