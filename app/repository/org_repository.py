from datetime import datetime, timezone
from app.db.firestore import db


class OrgRepository:
    """Repository for the 'orgs' Firestore collection."""

    def __init__(self):
        self.col = db.collection("orgs")

    def get_by_id(self, org_id: str) -> dict | None:
        doc = self.col.document(org_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        return None

    def create(self, name: str, org_id: str | None = None) -> dict:
        now = datetime.now(timezone.utc)
        data = {"name": name, "status": "ACTIVE", "created_at": now}
        if org_id:
            self.col.document(org_id).set(data)
            data["id"] = org_id
        else:
            _, doc_ref = self.col.add(data)
            data["id"] = doc_ref.id
        return data

    def get_all(self) -> list[dict]:
        docs = self.col.where("status", "==", "ACTIVE").stream()
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["id"] = doc.id
            results.append(data)
        return results

    def update_status(self, org_id: str, status: str) -> None:
        self.col.document(org_id).update({"status": status})
