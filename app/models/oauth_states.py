"""
DB model for the `oauth_states` Firestore collection.
Short-lived documents used to prevent CSRF during the TikTok OAuth flow.
Document ID = the state string itself for O(1) lookup.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class OAuthState:
    id: str          # Firestore document ID = state string
    state: str
    org_id: str      # org that initiated the TikTok connect flow
    issued_by: str   # Firebase UID of the admin who triggered the flow
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Serialisation ─────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: dict, doc_id: str = "") -> "OAuthState":
        return cls(
            id=doc_id or data.get("id", ""),
            state=data.get("state", ""),
            org_id=data.get("org_id", ""),
            issued_by=data.get("issued_by", ""),
            created_at=data.get("created_at") or datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict:
        return {
            "state": self.state,
            "org_id": self.org_id,
            "issued_by": self.issued_by,
            "created_at": self.created_at,
        }
