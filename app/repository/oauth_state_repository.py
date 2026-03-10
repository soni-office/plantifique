from datetime import datetime, timezone
from app.db.firestore import db


class OAuthStateRepository:

    def __init__(self):
        self.col = db.collection("oauth_states")

    def get_by_state(self, state: str) -> dict | None:
        """
        Use the state string itself as the document ID for O(1) lookup.
        No query needed — direct document fetch.
        """
        doc = self.col.document(state).get()
        if doc.exists:
            data = doc.to_dict()
            data["id"] = doc.id
            return data
        return None

    def create(self, state: str) -> dict:
        """Create an oauth state document using the state string as the document ID."""
        now = datetime.now(timezone.utc)
        data = {"state": state, "created_at": now}
        self.col.document(state).set(data)
        data["id"] = state
        return data

    def delete(self, state: str) -> None:
        """Delete the oauth state document by state string."""
        self.col.document(state).delete()