"""
DB model for the `orgs` Firestore collection.
Document ID = org_id (set explicitly on creation).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


OrgStatus = Literal["ACTIVE", "INACTIVE"]


@dataclass
class Org:
    id: str                          # Firestore document ID = org_id
    name: str
    status: OrgStatus = "ACTIVE"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Serialisation ─────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: dict, doc_id: str = "") -> "Org":
        return cls(
            id=doc_id or data.get("id", ""),
            name=data.get("name", ""),
            status=data.get("status", "ACTIVE"),
            created_at=data.get("created_at") or datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at,
        }
