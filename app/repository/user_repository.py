from datetime import datetime, timezone
from google.cloud import firestore
from google.cloud.firestore import FieldFilter
from app.db.firestore import db


class UserRepository:
    """
    Repository for the 'users' Firestore collection.
    """

    def __init__(self):
        self.col = db.collection("users")


    def get_by_id(self, user_id: str) -> dict | None:
        """O(1) fetch by Firestore document ID."""
        doc = self.col.document(user_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        return None

    def get_by_tiktok_open_id(self, open_id: str) -> dict | None:
        """
        Find a user by their TikTok open_id.
        Requires a single-field index on 'tiktok_open_id'.
        O(log N) with index.
        """
        docs = (
            self.col.where(filter=FieldFilter("tiktok_open_id", "==", open_id))
            .limit(1)
            .stream()
        )
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        return None

    def get_by_email(self, email: str) -> dict | None:
        docs = (
            self.col.where(filter=FieldFilter("email", "==", email.lower().strip()))
            .limit(1)
            .stream()
        )
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        return None

    def get_all_by_org(self, org_id: str) -> list[dict]:
        docs = (
            self.col.where(filter=FieldFilter("org_id", "==", org_id))
            .where(filter=FieldFilter("status", "==", "ACTIVE"))
            .stream()
        )
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(data)
        return results


    def create(
        self,
        org_id: str,
        uid: str | None = None,
        open_id: str | None = None,
        email: str | None = None,
        name: str | None = None,
        role: str = "ORG_MEMBER",
    ) -> dict:
        """
        Create a new user document.

        If ``uid`` is provided (Firebase UID from GCIP) it is used as the
        Firestore document ID so ``get_by_id(uid)`` works without a query.
        Falls back to an auto-generated ID for legacy / non-GCIP users.
        """
        now = datetime.now(timezone.utc)
        data = {
            "org_id": org_id,
            "tiktok_open_id": open_id,
            "email": email.lower().strip() if email else None,
            "name": name,
            "role": role,
            "status": "ACTIVE",
            "created_at": now,
            "last_login_at": now,
        }
        if uid:
            self.col.document(uid).set(data)
            data["id"] = uid
        else:
            _, doc_ref = self.col.add(data)
            data["id"] = doc_ref.id
        return data

    def touch_login(self, user_id: str) -> None:
        """Update last_login_at timestamp on every successful login."""
        self.col.document(user_id).update(
            {"last_login_at": datetime.now(timezone.utc)}
        )

    def update_status(self, user_id: str, status: str) -> None:
        """Activate or deactivate a user: 'ACTIVE' | 'DEACTIVATED'."""
        self.col.document(user_id).update({"status": status})