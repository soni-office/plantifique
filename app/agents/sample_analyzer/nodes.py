import os
from pydantic import BaseModel, Field
from langchain_google_vertexai import ChatVertexAI

from app.agents.tools import (
    fetch_sample_by_id, 
    get_tier, 
    TIER_3_THRESHOLDS, 
    TIER_4_THRESHOLDS
)
from app.agents.sample_analyzer.state import SREvaluationState
from app.agents.sample_analyzer.prompts import CREATOR_EVALUATION_PROMPT
from app.services.tiktok.creator_service import TikTokCreatorService
from app.services.tiktok.product_service import TikTokProductService
import json

class ScoreResult(BaseModel):
    """Pydantic model to enforce structured JSON output from Vertex AI."""
    score: int = Field(description="Score out of 100 representing creator-product fit")
    reasoning: str = Field(description="Brief explanation of the score")

def fetch_data_node(state: SREvaluationState) -> dict:
    """Fetches sample request data and configures thresholds based on tier."""
    sample_id = state["sample_request_id"]
    access_token = state.get("access_token")
    shop_cipher = state.get("shop_cipher")
    
    sample = fetch_sample_by_id(sample_id, access_token=access_token, shop_cipher=shop_cipher)

    if not sample:
        return {
            "tier": "UNKNOWN",
            "final_decision": "ERROR",
            "decision_reason": f"Sample request '{sample_id}' not found.",
        }

    creator = sample["creator"]
    product = sample["product"]
    product_title = product["title"]
    tier = get_tier(product_title)

    # Set thresholds depending on tier
    thresholds = {}
    if tier == "TIER_3":
        thresholds = TIER_3_THRESHOLDS.get(product_title, {})
    elif tier == "TIER_4":
        thresholds = TIER_4_THRESHOLDS.get(product_title, {})

    return {
        "tier": tier,
        "creator_data": creator,
        "product_data": product,
        "product_title": product_title,
        "thresholds": thresholds,
        "post_rate": float(creator.get("fulfillment_percentage", 0)),
    }

def validation_node(state: SREvaluationState) -> dict:
    """Stage 1: Strict Heuristic Rules (GMV/Follower Thresholds)"""
    creator = state.get("creator_data", {})
    thresholds = state.get("thresholds", {})
    tier = state.get("tier", "UNKNOWN")

    region = creator.get("selection_region", "UNKNOWN")
    followers = creator.get("follower_count", 0)
    gmv = float(creator.get("gmv", {}).get("amount", 0))
    post_rate = state.get("post_rate", 0.0)

    min_gmv = thresholds.get("min_gmv", 0)
    min_followers = thresholds.get("min_followers", 0)
    min_post_rate = thresholds.get("min_post_rate", 0)

    print(f"[DEBUG] Validation Check for {creator.get('username')}: region={region}, tier={tier}, gmv={gmv}, followers={followers}, post_rate={post_rate}")



    # Reject if Tier 3/4 thresholds are not met
    if tier in ("TIER_3", "TIER_4"):
        if gmv < min_gmv:
             print(f"[DEBUG] Filter Failed: GMV {gmv} < {min_gmv}")
             return {"filters_passed": False, "validation_reason": f"Failed GMV threshold. Has ${gmv:,.2f}, needs ${min_gmv:,.2f}."}
        if followers < min_followers:
             print(f"[DEBUG] Filter Failed: Followers {followers} < {min_followers}")
             return {"filters_passed": False, "validation_reason": f"Failed Follower threshold. Has {followers:,}, needs {min_followers:,}."}
        if post_rate < min_post_rate:
             print(f"[DEBUG] Filter Failed: Post Rate {post_rate} < {min_post_rate}")
             return {"filters_passed": False, "validation_reason": f"Failed Post Rate threshold. Has {post_rate}%, needs {min_post_rate}%."}

    print(f"[DEBUG] Validation Passed for {creator.get('username')}")

    # If it's Tier 3 or 4 and it reached here, it passed.
    if tier in ("TIER_3", "TIER_4"):
        return {
            "filters_passed": True,
            "validation_reason": "Passed all baseline threshold checks."
        }

    # For Tier 1/2/5, we explicitly skip strict filtering
    return {
        "filters_passed": None, 
        "validation_reason": f"Heuristic filters skipped for {tier} (Handling is manual/white-glove)."
    }

def flag_internal_node(state: SREvaluationState) -> dict:
    """Flags requests that bypass the AI for internal human-led review."""
    tier = state.get("tier", "UNKNOWN")
    reasons = {
        "TIER_1": f"Retainer creator ({tier}) — handled by internal team (white-glove service).",
        "TIER_2": f"Exception list creator ({tier}) — requires manual internal review (Discord/DMs).",
        "TIER_5": f"Product not in strategic focus ({tier}) — flagged for internal review only.",
        "UNKNOWN": f"Product tier could not be determined ({tier}) — flagged for manual review.",
    }

    return {
        "final_decision": "FLAG_INTERNAL",
        "decision_reason": reasons.get(tier, "Flagged for internal review."),
    }

def llm_score_node(state: SREvaluationState) -> dict:
    """Stage 2: Invokes Gemini for a rich Profile/Product Compatibility Check"""
    creator = state.get("creator_data", {})
    product = state.get("product_data", {})
    
    creator_open_id = creator.get("creator_open_id")
    product_id = product.get("id")
    access_token = state.get("access_token")
    shop_cipher = state.get("shop_cipher")
    
    rich_creator_dict = {}
    rich_product_dict = {}

    if access_token:
        # 1. Fetch rich creator detail
        if creator_open_id:
            res_c = TikTokCreatorService.get_creator_detail(access_token, shop_cipher, creator_open_id)
            if res_c and isinstance(res_c, dict) and "data" in res_c:
                print(f"[DEBUG] Successfully fetched rich creator detail for {creator_open_id}")
                rich_creator_dict = res_c.get("data", {}).get("creator", {})
            else:
                print(f"[DEBUG] Failed to fetch rich details for {creator_open_id}")

        # 2. Fetch rich product detail
        if product_id:
            res_p = TikTokProductService.get_product_by_id(access_token, shop_cipher, product_id)
            if res_p and isinstance(res_p, dict) and "data" in res_p:
                print(f"[DEBUG] Successfully fetched rich product detail for {product_id}")
                rich_product_dict = res_p.get("data", {})
            else:
                print(f"[DEBUG] Failed to fetch rich product details for {product_id}")

    llm = ChatVertexAI(
        model_name="gemini-2.0-flash",
        project="tiktok-ai-agent-488417",
        location="us-central1",
        temperature=0,
    )
    structured_llm = llm.with_structured_output(ScoreResult)

    prompt_str = CREATOR_EVALUATION_PROMPT.format(
        product_title=state.get("product_title"),
        tier=state.get("tier"),
        product_json=json.dumps(rich_product_dict, indent=2),
        creator_json=json.dumps(rich_creator_dict, indent=2)
    )

    result = structured_llm.invoke(prompt_str)

    return {
        "llm_score": result.score,
        "llm_reasoning": result.reasoning,
        "compatibility_status": "PROCESSED",
        "rich_creator_detail": rich_creator_dict,
        "rich_product_detail": rich_product_dict
    }

def decision_node(state: SREvaluationState) -> dict:
    """Makes a final ACCEPT/REJECT decision based on Stage 1 AND Stage 2 outputs."""
    filters_passed = state.get("filters_passed", False)
    val_reason = state.get("validation_reason", "Failed validation.")
    tier = state.get("tier", "UNKNOWN")

    # 1. Did it fail Stage 1 logic immediately?
    if not filters_passed:
         return {
             "final_decision": "REJECT",
             "decision_reason": f"[Stage 1 Filter Failed] {val_reason}\n\nProduct Category: {tier}",
             "compatibility_status": "SKIPPED"
         }

    # 2. It passed Stage 1, so read the Stage 2 LLM Score
    score = state.get("llm_score", 0)
    threshold = state.get("threshold", 70)
    llm_reasoning = state.get("llm_reasoning", "No reasoning provided.")

    if score >= threshold:
        return {
            "final_decision": "ACCEPT",
            "decision_reason": f"[Stage 2 Pass] Compatibility Score: {score}/100.\n\n{llm_reasoning}\n\nProduct Category: {tier}"
        }
        
    return {
        "final_decision": "POTENTIAL_ACCEPT",
        "decision_reason": f"[Stage 2 Fail] Compatibility Score: {score}/100.\n\n{llm_reasoning}\n\nProduct Category: {tier}"
    }

def route_after_validation(state: SREvaluationState) -> str:
    """Routing after Step 1 Validation."""
    if state.get("final_decision") == "ERROR":
        return "end"

    filters_passed = state.get("filters_passed", False)
    if not filters_passed:
        # Failed standard thresholds -> Go straight to decision (bypassing LLM API call)
        return "decision"
        
    # Passed standard thresholds!
    tier = state.get("tier", "UNKNOWN")
    if tier in ("TIER_1", "TIER_2", "TIER_5", "UNKNOWN"):
        return "flag_internal"
    
    # Needs LLM Compatibility evaluation!
    return "llm_score"
