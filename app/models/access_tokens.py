"""
DB model for the `access_tokens` Firestore collection.
Stores org-level TikTok OAuth tokens. Document ID = org_id.
Tokens are encrypted at rest by the repository layer; this model works with
the decrypted plaintext values.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal, Optional


TokenStatus = Literal["ACTIVE", "REVOKED"]


@dataclass
class AccessToken:
    id: str                              # Firestore document ID = org_id
    org_id: str
    issued_by: str                       # Firebase UID of the admin who connected TikTok
    tiktok_open_id: str
    access_token: str                    # decrypted; never stored as plaintext in Firestore
    refresh_token: str                   # decrypted; never stored as plaintext in Firestore
    access_token_expires_at: int         # Unix timestamp
    status: TokenStatus = "ACTIVE"
    issued_on: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_refreshed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    refresh_token_expires_at: Optional[int] = None

    # ── Serialisation ─────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: dict, doc_id: str = "") -> "AccessToken":
        return cls(
            id=doc_id or data.get("id", ""),
            org_id=data.get("org_id", ""),
            issued_by=data.get("issued_by", ""),
            tiktok_open_id=data.get("tiktok_open_id", ""),
            access_token=data.get("access_token", ""),   # already decrypted by repo
            refresh_token=data.get("refresh_token", ""),  # already decrypted by repo
            access_token_expires_at=data.get("access_token_expires_at", 0),
            refresh_token_expires_at=data.get("refresh_token_expires_at"),
            status=data.get("status", "ACTIVE"),
            issued_on=data.get("issued_on") or datetime.now(timezone.utc),
            last_refreshed_at=data.get("last_refreshed_at") or datetime.now(timezone.utc),
            updated_at=data.get("updated_at") or datetime.now(timezone.utc),
        )

    def to_dict(self) -> dict:
        """
        Returns a dict suitable for writing to Firestore.
        NOTE: the repository layer encrypts access_token / refresh_token before writing.
        """
        return {
            "org_id": self.org_id,
            "issued_by": self.issued_by,
            "issued_on": self.issued_on,
            "tiktok_open_id": self.tiktok_open_id,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "access_token_expires_at": self.access_token_expires_at,
            "refresh_token_expires_at": self.refresh_token_expires_at,
            "last_refreshed_at": self.last_refreshed_at,
            "status": self.status,
            "updated_at": self.updated_at,
        }
