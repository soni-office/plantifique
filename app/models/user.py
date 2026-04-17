"""
DB model for the `users` Firestore collection.
Document ID = Firebase UID (set explicitly so get_by_id works without a query).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional


UserRole   = Literal["SUPER_ADMIN", "ORG_ADMIN", "ORG_MEMBER"]
UserStatus = Literal["ACTIVE", "DEACTIVATED"]


@dataclass
class User:
    id: str                              # Firestore document ID = Firebase UID
    org_id: str
    role: UserRole = "ORG_MEMBER"
    status: UserStatus = "ACTIVE"
    email: Optional[str] = None
    name: Optional[str] = None
    tiktok_open_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_login_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Serialisation ─────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: dict, doc_id: str = "") -> "User":
        return cls(
            id=doc_id or data.get("id", ""),
            org_id=data.get("org_id", ""),
            role=data.get("role", "ORG_MEMBER"),
            status=data.get("status", "ACTIVE"),
            email=data.get("email"),
            name=data.get("name"),
            tiktok_open_id=data.get("tiktok_open_id"),
            created_at=data.get("created_at") or datetime.now(timezone.utc),
            last_login_at=data.get("last_login_at") or datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict:
        return {
            "org_id": self.org_id,
            "role": self.role,
            "status": self.status,
            "email": self.email,
            "name": self.name,
            "tiktok_open_id": self.tiktok_open_id,
            "created_at": self.created_at,
            "last_login_at": self.last_login_at,
        }
