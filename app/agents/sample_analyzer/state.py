from typing import Any, Dict, Optional
from typing_extensions import TypedDict


class SREvaluationState(TypedDict):
    """State object passed between every node in the SR evaluation graph."""

    # -- Inputs --
    sample_request_id: str
    threshold: int  
    access_token: Optional[str]
    shop_cipher: Optional[str]

    # -- Populated by fetch_data_node --
    tier: Optional[str]
    creator_data: Optional[Dict[str, Any]]
    product_data: Optional[Dict[str, Any]]
    product_title: Optional[str]
    thresholds: Optional[Dict[str, Any]]  # min_gmv / min_followers / min_post_rate for the product
    post_rate: Optional[float]            # Creator's TikTok post rate (%)

    # -- Populated by validation_node (Stage 1) --
    filters_passed: Optional[bool]
    validation_reason: Optional[str]

    # -- Populated by compatibility_node (Stage 2) --
    llm_score: Optional[int]       
    llm_reasoning: Optional[str]
    compatibility_status: Optional[str] # "PROCESSED" or "SKIPPED"
    rich_creator_detail: Optional[Dict[str, Any]]
    rich_product_detail: Optional[Dict[str, Any]]

    # -- Populated by decision_node --
    final_decision: Optional[str]   
    decision_reason: Optional[str]
