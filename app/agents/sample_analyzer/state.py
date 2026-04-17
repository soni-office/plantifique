from typing import Any, Dict, List, Optional
from typing_extensions import TypedDict


class SREvaluationState(TypedDict):
    """State object passed between every node in the SR evaluation graph."""

    # -- Inputs --
    sample_request_id: str
    threshold: int
    access_token: Optional[str]
    shop_cipher: Optional[str]

    # -- Populated by fetch_data_node --
    org_id: Optional[str]
    tier: Optional[str]
    creator_data: Optional[Dict[str, Any]]        # shallow data from sample DB record
    rich_creator_data: Optional[Dict[str, Any]]   # full detail from TikTok creator detail API
    product_data: Optional[Dict[str, Any]]
    product_title: Optional[str]
    product_description: Optional[str]
    thresholds: Optional[Dict[str, Any]]
    post_rate: Optional[float]

    # -- Populated by validation_node (Stage 1) --
    filters_passed: Optional[bool]
    validation_reason: Optional[str]

    # -- Populated by roi_check_node (Stage 1b — Tier 4 only) --
    roi_passed: Optional[bool]          # None = not applicable (non-Tier4), True/False = pass/fail
    roi_reason: Optional[str]

    # -- Populated by fetch_aesthetic_data_node --
    recent_videos: Optional[List[Dict[str, Any]]]

    # -- Populated by commerce_evaluation_node (Phase 2) --
    commerce_score: Optional[int]
    commerce_reasoning: Optional[str]
    compatibility_status: Optional[str]  # "PROCESSED" or "SKIPPED"

    rich_creator_detail: Optional[Dict[str, Any]]
    rich_product_detail: Optional[Dict[str, Any]]

    # -- Populated by aesthetic_evaluation_node (Phase 3) --
    aesthetic_score: Optional[int]
    aesthetic_reasoning: Optional[str]
    top_3_video_urls: Optional[List[str]]

    # -- Populated by visual_evaluation_node (Phase 4) --
    visual_score: Optional[int]
    visual_reasoning: Optional[str]
    matched_patterns: Optional[List[str]]
    missing_patterns: Optional[List[str]]

    # -- Populated by decision_node --
    final_decision: Optional[str]
    decision_reason: Optional[str]
