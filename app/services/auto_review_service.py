"""
Auto-review service — applies rule-based approve/reject decisions
immediately after AI analysis completes.

Decision rules (evaluated in priority order):
  1. GMV < $300                            → AUTO REJECT  (always)
  2. post_rate < 50% AND GMV < $1000       → AUTO REJECT
  3. Creator already APPROVED elsewhere    → AUTO REJECT  (duplicate guard)
  4. AI final_decision == "ACCEPT"         → AUTO APPROVE
  5. GMV > $10K AND post_rate > 65%        → AUTO APPROVE
  6. Everything else                       → Leave as PENDING_REVIEW

Post-rate note:
  TikTok returns post_rate in basis-point-like units where the raw value
  is divided by 100 for display (e.g. raw 5000 → displayed 50.00%).
  All thresholds here use raw values: 50% = 5000, 65% = 6500.
"""
import logging


from google.cloud.firestore import FieldFilter

from app.db.firestore import db

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────
GMV_HARD_REJECT     = 300       # Always reject if GMV < $300
GMV_LOW_THRESHOLD   = 1000      # Used with post_rate condition
GMV_HIGH_THRESHOLD  = 10_000   # Auto-approve if GMV > $10K
POST_RATE_LOW       = 5000      # 50%  (raw units ÷ 100 = display %)
POST_RATE_HIGH      = 6500      # 65%


class AutoReviewService:

    def __init__(self):
        self._col = db.collection("sample_analyses")

    # ── Public entry point ────────────────────────────────────────────────────

    def run(
        self,
        sample_id: str,
        org_id: str,
        result: dict,           # raw agent result dict (in-memory, no re-fetch needed)
    ) -> dict:
        """
        Evaluate auto-review rules and apply APPROVE/REJECT if warranted.
        Returns a dict describing the action taken.
        """
        gmv, post_rate = self._get_metrics(result)
        final_decision = (result.get("final_decision") or "").upper()
        creator_open_id = self._get_creator_open_id(sample_id)

        has_duplicate = self._check_duplicate(
            creator_open_id=creator_open_id,
            org_id=org_id,
            current_sample_id=sample_id,
        ) if creator_open_id else False

        action, reason = self._apply_rules(gmv, post_rate, final_decision, has_duplicate)

        if action is None:
            logger.info(
                "AutoReview: sample_id=%s → PENDING_REVIEW (no auto-rule matched). gmv=%s post_rate=%s",
                sample_id, gmv, post_rate,
            )
            return {"action": "PENDING_REVIEW", "reason": "No auto-rule matched — needs human review."}

        # Map internal action to TikTok API value
        review_result = "APPROVE" if action == "APPROVE" else "REJECT"
        reject_reason = "OTHER" if action == "REJECT" else None
        internal_status = "APPROVED" if action == "APPROVE" else "REJECTED"

        # Use the unified review status service
        try:
            from app.services.sample_analysis_service import get_sample_analysis_service
            service = get_sample_analysis_service()
            service.update_review_status(
                org_id=org_id,
                sample_id=sample_id,
                internal_status=internal_status,
                review_result=review_result,
                reject_reason=reject_reason,
                db_reason=reason,
                user_id="auto_review_bot"
            )
        except Exception as e:
            logger.error(
                "AutoReview: unified status update failed for sample_id=%s: %s",
                sample_id, e,
            )

        return {"action": internal_status, "reason": reason}

    # ── Rule engine ───────────────────────────────────────────────────────────

    def _apply_rules(
        self,
        gmv: float | None,
        post_rate: float | None,
        final_decision: str,
        has_duplicate: bool,
    ) -> tuple[str | None, str]:
        """
        Returns (action, reason) where action is "APPROVE", "REJECT", or None.
        None means leave as PENDING_REVIEW for a human.
        """
        # Rule 1 — hard GMV floor (skip if exactly 0, leave for client)
        if gmv is not None and 0 < gmv < GMV_HARD_REJECT:
            return "REJECT", f"GMV ${gmv:.0f} is below the $300 minimum threshold."

        # Rule 2 — low post rate + low GMV combined (skip if exactly 0, leave for client)
        if post_rate is not None and post_rate < POST_RATE_LOW and gmv is not None and 0 < gmv < GMV_LOW_THRESHOLD:
            display_rate = post_rate / 100
            return (
                "REJECT",
                f"Post rate {display_rate:.2f}% is below 50% and GMV ${gmv:.0f} is under $1,000.",
            )

        # Rule 3 — duplicate guard (same creator already approved for another product)
        if has_duplicate:
            return (
                "REJECT",
                "Creator is already approved for another sample request in this campaign.",
            )

        # Rule 4 — AI says ACCEPT AND strong GMV + post rate
        if final_decision == "ACCEPT" and gmv is not None and gmv > GMV_HIGH_THRESHOLD and post_rate is not None and post_rate > POST_RATE_HIGH:
            display_rate = post_rate / 100
            return (
                "APPROVE",
                f"AI ACCEPTED and GMV (${gmv:,.0f}) exceeds $10K and post rate ({display_rate:.2f}%) exceeds 65%.",
            )

        # No rule matched — leave for human review
        return None, ""

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_metrics(self, result: dict) -> tuple[float | None, float | None]:
        """Extract GMV (USD float) and raw post_rate from the agent result dict."""
        creator_detail = result.get("rich_creator_detail") or {}

        # GMV
        gmv_raw = (creator_detail.get("gmv") or {}).get("amount")
        try:
            gmv = float(gmv_raw) if gmv_raw is not None else None
        except (ValueError, TypeError):
            gmv = None

        # Post rate — stored as raw units (÷ 100 = display %)
        pr_raw = creator_detail.get("post_rate")
        try:
            post_rate = float(pr_raw) if pr_raw is not None else None
        except (ValueError, TypeError):
            post_rate = None

        return gmv, post_rate

    def _get_creator_open_id(self, sample_id: str) -> str | None:
        """Read creator_open_id from the Firestore doc (already saved by upsert_from_tiktok)."""
        doc = self._col.document(sample_id).get()
        if not doc.exists:
            return None
        return (doc.to_dict().get("creator") or {}).get("creator_open_id")

    def _check_duplicate(
        self,
        creator_open_id: str,
        org_id: str,
        current_sample_id: str,
    ) -> bool:
        """
        Returns True if this creator already has an APPROVED request in this org
        (excluding the current sample being evaluated).

        Requires a Firestore composite index:
          collection: sample_analyses
          fields: org_id (ASC), creator.creator_open_id (ASC), review_status (ASC)
        """
        docs = (
            self._col
            .where(filter=FieldFilter("org_id", "==", org_id))
            .where(filter=FieldFilter("creator.creator_open_id", "==", creator_open_id))
            .where(filter=FieldFilter("review_status", "==", "APPROVED"))
            .limit(2)
            .stream()
        )
        for doc in docs:
            if doc.id != current_sample_id:
                logger.info(
                    "AutoReview: duplicate found — creator=%s already approved in doc=%s",
                    creator_open_id, doc.id,
                )
                return True
        return False
