from datetime import datetime, timezone
from app.db.firestore import db
from app.core.token_crypto import token_crypto


class AccessTokenRepository:
    """
    Stores TikTok OAuth tokens at the ORG level.
    Document ID = org_id → O(1) lookup. Tokens are encrypted at rest.
    """

    def __init__(self):
        self.col = db.collection("access_tokens")
        self.crypto = token_crypto

    def get_by_org(self, org_id: str) -> dict | None:
        doc = self.col.document(org_id).get()
        if not doc.exists:
            return None
        data = doc.to_dict()
        data["id"] = doc.id
        data["access_token"] = self.crypto.decrypt(data.get("access_token"))
        data["refresh_token"] = self.crypto.decrypt(data.get("refresh_token"))
        return data

    def upsert(
        self,
        org_id: str,
        issued_by: str,
        tiktok_open_id: str,
        access_token: str,
        refresh_token: str,
        access_token_expires_at: int,
        refresh_token_expires_at: int | None = None,
    ) -> dict:
        now = datetime.now(timezone.utc)
        data = {
            "org_id": org_id,
            "issued_by": issued_by,
            "issued_on": now,
            "tiktok_open_id": tiktok_open_id,
            "access_token": self.crypto.encrypt(access_token),
            "refresh_token": self.crypto.encrypt(refresh_token),
            "access_token_expires_at": access_token_expires_at,
            "refresh_token_expires_at": refresh_token_expires_at,
            "last_refreshed_at": now,
            "status": "ACTIVE",
            "updated_at": now,
        }
        self.col.document(org_id).set(data)
        data["id"] = org_id
        data["access_token"] = access_token
        data["refresh_token"] = refresh_token
        return data

    def update_tokens(self, org_id: str, fields: dict) -> None:
        if "access_token" in fields:
            fields["access_token"] = self.crypto.encrypt(fields["access_token"])
        if "refresh_token" in fields:
            fields["refresh_token"] = self.crypto.encrypt(fields["refresh_token"])
        fields["last_refreshed_at"] = datetime.now(timezone.utc)
        fields["updated_at"] = datetime.now(timezone.utc)
        self.col.document(org_id).update(fields)

    def revoke(self, org_id: str) -> None:
        self.col.document(org_id).update(
            {"status": "REVOKED", "updated_at": datetime.now(timezone.utc)}
        )
