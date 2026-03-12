"""
In-memory store for manual review states and AI feedback on Sample Requests.
This is intentionally ephemeral (resets on server restart) until a DB layer is added.
"""
from typing import Dict, Optional, Any
from datetime import datetime, timezone


# Maps sample_request_id -> manual review status
# Default is "PENDING" for any SR not explicitly updated.
_sr_review_states: Dict[str, str] = {}

# Maps sample_request_id -> { "rating": "up"|"down", "comment": str, "updated_at": str }
_sr_feedback: Dict[str, Dict[str, Any]] = {}

VALID_REVIEW_STATUSES = {"PENDING", "ACCEPTED", "REJECTED", "UNDER_REVIEW"}


def get_review_status(sample_id: str) -> str:
    return _sr_review_states.get(sample_id, "PENDING")


def set_review_status(sample_id: str, status: str) -> None:
    if status not in VALID_REVIEW_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {VALID_REVIEW_STATUSES}")
    _sr_review_states[sample_id] = status


def get_feedback(sample_id: str) -> Optional[Dict[str, Any]]:
    return _sr_feedback.get(sample_id)


def set_feedback(sample_id: str, rating: str, comment: str = "") -> Dict[str, Any]:
    if rating not in ("up", "down"):
        raise ValueError("Rating must be 'up' or 'down'")
    record = {
        "rating": rating,
        "comment": comment,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _sr_feedback[sample_id] = record
    return record
