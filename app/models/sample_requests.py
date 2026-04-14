"""
DB model for the `sample_analyses` Firestore collection.
Document ID = TikTok application ID (tiktok_sample_id).

Analysis status lifecycle:
  NOT_STARTED  — synced from TikTok, no analysis triggered yet (default)
  QUEUED       — user clicked Analyze; agent job is enqueued / in-flight
  COMPLETED    — agent finished successfully
  FAILED       — agent raised an error

Review status lifecycle:
  PENDING_REVIEW → APPROVED | REJECTED  (human decision after analysis)

TTL: `delete_at` is set when a sample is marked PROCESSED_ON_SHOP; Firestore
auto-deletes the document after that timestamp via a TTL policy.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional


AnalysisStatus = Literal["NOT_STARTED", "QUEUED", "COMPLETED", "FAILED"]
ReviewStatus   = Literal["PENDING_REVIEW", "APPROVED", "REJECTED"]
TikTokStatus   = Literal["PENDING", "PROCESSED_ON_SHOP"]
FinalDecision  = Literal["ACCEPT", "REJECT", "FLAG_INTERNAL", "POTENTIAL_ACCEPT"]
FeedbackRating = Literal["up", "down"]


@dataclass
class SampleAnalysis:
    """
    Represents one row in `sample_analyses`.

    `creator` and `product` are raw embedded TikTok API sub-documents stored
    as-is during sync; their exact shape depends on the TikTok response.
    """
    id: str                                  # Firestore doc ID = tiktok_sample_id
    org_id: str
    tiktok_sample_id: str

    # ── TikTok-sourced fields (updated on every sync) ─────────────────────
    tiktok_status: TikTokStatus = "PENDING"
    commission_rate: Optional[str] = None
    available_quantity: Optional[int] = None
    is_approvable: Optional[bool] = None
    approve_expiration_time: Optional[int] = None  # Unix timestamp
    order_id: Optional[str] = None
    creator: Dict[str, Any] = field(default_factory=dict)   # raw TikTok creator payload
    product: Dict[str, Any] = field(default_factory=dict)   # raw TikTok product payload
    last_synced_at: Optional[datetime] = None

    # ── Analysis state ────────────────────────────────────────────────────
    analysis_status: AnalysisStatus = "NOT_STARTED"
    review_status: ReviewStatus = "PENDING_REVIEW"
    first_seen_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Agent output (populated after analysis completes) ─────────────────
    final_decision: Optional[FinalDecision] = None
    tier: Optional[str] = None
    filters_passed: Optional[bool] = None
    validation_reason: Optional[str] = None

    # Phase 2 — Commerce evaluation
    commerce_score: Optional[int] = None         # Commerce/audience fit score 0–100
    commerce_reasoning: Optional[str] = None     # Commerce reasoning from LLM

    # Phase 3 — Aesthetic evaluation
    aesthetic_score: Optional[int] = None       # Visual/aesthetic fit score 0–100
    aesthetic_reasoning: Optional[str] = None   # Aesthetic reasoning from LLM
    top_3_video_urls: List[str] = field(default_factory=list)  # Evidence video URLs

    # Final decision explanation (combined from both phases)
    decision_reason: Optional[str] = None
    processed_at: Optional[datetime] = None

    # ── Human feedback ────────────────────────────────────────────────────
    feedback_rating: Optional[FeedbackRating] = None
    feedback_comment: str = ""

    # ── Timestamps ────────────────────────────────────────────────────────
    updated_at: Optional[datetime] = None
    delete_at: Optional[datetime] = None   # Firestore TTL — set when PROCESSED_ON_SHOP

    # ── Serialisation ─────────────────────────────────────────────────────

    @classmethod
    def from_dict(cls, data: dict, doc_id: str = "") -> "SampleAnalysis":
        return cls(
            id=doc_id or data.get("id", ""),
            org_id=data.get("org_id", ""),
            tiktok_sample_id=data.get("tiktok_sample_id", ""),
            tiktok_status=data.get("tiktok_status", "PENDING"),
            commission_rate=data.get("commission_rate"),
            available_quantity=data.get("available_quantity"),
            is_approvable=data.get("is_approvable"),
            approve_expiration_time=data.get("approve_expiration_time"),
            order_id=data.get("order_id"),
            creator=data.get("creator") or {},
            product=data.get("product") or {},
            last_synced_at=data.get("last_synced_at"),
            analysis_status=data.get("analysis_status", "NOT_STARTED"),
            review_status=data.get("review_status", "PENDING_REVIEW"),
            first_seen_at=data.get("first_seen_at") or datetime.now(timezone.utc),
            final_decision=data.get("final_decision"),
            tier=data.get("tier"),
            filters_passed=data.get("filters_passed"),
            validation_reason=data.get("validation_reason"),
            commerce_score=data.get("commerce_score"),
            commerce_reasoning=data.get("commerce_reasoning"),
            aesthetic_score=data.get("aesthetic_score"),
            aesthetic_reasoning=data.get("aesthetic_reasoning"),
            top_3_video_urls=data.get("top_3_video_urls") or [],
            decision_reason=data.get("decision_reason"),
            processed_at=data.get("processed_at"),
            feedback_rating=data.get("feedback_rating"),
            feedback_comment=data.get("feedback_comment", ""),
            updated_at=data.get("updated_at"),
            delete_at=data.get("delete_at"),
        )

    def to_dict(self) -> dict:
        return {
            "org_id": self.org_id,
            "tiktok_sample_id": self.tiktok_sample_id,
            "tiktok_status": self.tiktok_status,
            "commission_rate": self.commission_rate,
            "available_quantity": self.available_quantity,
            "is_approvable": self.is_approvable,
            "approve_expiration_time": self.approve_expiration_time,
            "order_id": self.order_id,
            "creator": self.creator,
            "product": self.product,
            "last_synced_at": self.last_synced_at,
            "analysis_status": self.analysis_status,
            "review_status": self.review_status,
            "first_seen_at": self.first_seen_at,
            "final_decision": self.final_decision,
            "tier": self.tier,
            "filters_passed": self.filters_passed,
            "validation_reason": self.validation_reason,
            "commerce_score": self.commerce_score,
            "commerce_reasoning": self.commerce_reasoning,
            "aesthetic_score": self.aesthetic_score,
            "aesthetic_reasoning": self.aesthetic_reasoning,
            "top_3_video_urls": self.top_3_video_urls,
            "decision_reason": self.decision_reason,
            "processed_at": self.processed_at,
            "feedback_rating": self.feedback_rating,
            "feedback_comment": self.feedback_comment,
            "updated_at": self.updated_at,
            "delete_at": self.delete_at,
        }

    def get_review_status(self) -> ReviewStatus:
        return self.review_status

    def get_feedback(self) -> dict:
        return {
            "rating": self.feedback_rating,
            "comment": self.feedback_comment,
        }

    def get_analysis_result(self) -> dict:
        """Return analysis fields in the normalised shape the service/frontend expects."""
        return {
            "sample_request_id": self.tiktok_sample_id,
            "final_decision": self.final_decision,
            "tier": self.tier,
            "filters_passed": self.filters_passed,
            "validation_reason": self.validation_reason,
            "commerce_score": self.commerce_score,
            "commerce_reasoning": self.commerce_reasoning,
            "aesthetic_score": self.aesthetic_score,
            "aesthetic_reasoning": self.aesthetic_reasoning,
            "top_3_video_urls": self.top_3_video_urls,
            "decision_reason": self.decision_reason,
        }
