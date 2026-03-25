import json
import logging
import os

from pydantic import BaseModel, Field
from langchain_google_vertexai import ChatVertexAI

from app.agents.tools import (
    fetch_sample_by_id,
    get_tier,
    TIER_3_THRESHOLDS,
    TIER_4_THRESHOLDS,
)
from app.agents.sample_analyzer.state import SREvaluationState
from app.agents.sample_analyzer.prompts import (
    CREATOR_EVALUATION_PROMPT,
    AESTHETIC_EVALUATION_PROMPT
)
from app.core.config import settings
from app.services.tiktok.creator_service import TikTokCreatorService
from app.services.tiktok.product_service import TikTokProductService
from app.services.tikapi.client import TikApiService

logger = logging.getLogger(__name__)


class CommerceScoreResult(BaseModel):
    """Structured output schema for Vertex AI Phase 2."""
    score: int = Field(description="Score out of 100 representing commerce/audience fit")
    reasoning: str = Field(description="2-3 sentences explaining the compatibility decision")

class AestheticScoreResult(BaseModel):
    """Structured output schema for Vertex AI Phase 3."""
    aesthetic_score: int = Field(description="Score out of 100 representing aesthetic visual fit")
    reasoning: str = Field(description="2-3 sentences explaining the aesthetic compatibility")
    top_3_video_urls: list[str] = Field(
        default_factory=list,
        description="Top 3 video URLs (from recent_videos web_url) that best prove this creator belongs in the product niche. Empty list if no videos were available."
    )


def _sanitize_product(raw: dict) -> dict:
    """Strip noisy fields from TikTok product API response before sending to LLM."""
    if not raw:
        return {}
    return {
        "id": raw.get("id"),
        "title": raw.get("title"),
        "description": raw.get("description"),
        "status": raw.get("status"),
        "listing_quality_tier": raw.get("listing_quality_tier"),
        "price_usd": (
            raw.get("skus", [{}])[0].get("price", {}).get("sale_price")
            if raw.get("skus") else None
        ),
        "inventory_qty": (
            raw.get("skus", [{}])[0].get("inventory", [{}])[0].get("quantity")
            if raw.get("skus") else None
        ),
        "category": [c.get("local_name") for c in raw.get("category_chains", [])],
        "key_attributes": {
            a.get("name"): [v.get("name") for v in a.get("values", [])]
            for a in raw.get("product_attributes", [])
            if a.get("name") not in {
                "CA Prop 65: Repro. Chems", "CA Prop 65: Carcinogens",
                "Flammable Liquid", "Dangerous Goods Or Hazardous Materials",
            }
        },
    }


def _sanitize_video(v_list: list) -> list:
    """Strip binary URLs from video metadata for the LLM prompt."""
    if not v_list:
        return []
    clean = []
    for v in v_list:
        clean.append({
            "caption": v.get("caption"),
            "likes": v.get("likes"),
            "comments_count": v.get("comments_count"),
            "plays": v.get("plays"),
            "language": v.get("language"),
            "quality": v.get("quality"),
            "is_hd": v.get("is_hd"),
            "top_comments": v.get("top_comments"),
            "web_url": v.get("web_url"),
        })
    return clean


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

    logger.debug("Validation Check for %s: region=%s, tier=%s, gmv=%s, followers=%s, post_rate=%s", 
                 creator.get('username'), region, tier, gmv, followers, post_rate)

    # Reject if Tier 3/4 thresholds are not met
    if tier in ("TIER_3", "TIER_4"):
        if gmv < min_gmv:
             logger.warning("Filter Failed: GMV %s < %s", gmv, min_gmv)
             return {"filters_passed": False, "validation_reason": f"Failed GMV threshold. Has ${gmv:,.2f}, needs ${min_gmv:,.2f}."}
        if followers < min_followers:
             logger.warning("Filter Failed: Followers %s < %s", followers, min_followers)
             return {"filters_passed": False, "validation_reason": f"Failed Follower threshold. Has {followers:,}, needs {min_followers:,}."}
        if post_rate < min_post_rate:
             logger.warning("Filter Failed: Post Rate %s < %s", post_rate, min_post_rate)
             return {"filters_passed": False, "validation_reason": f"Failed Post Rate threshold. Has {post_rate}%, needs {min_post_rate}%."}

    logger.info("Validation Passed for %s", creator.get('username'))

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

def fetch_aesthetic_data_node(state: SREvaluationState) -> dict:
    """
    Stage 1.5: Fetch the creator's top 10 public TikTok videos via TikAPI.

    """
    creator = state.get("creator_data") or {}
    username = (
        creator.get("username")
        or creator.get("handle")
        or creator.get("creator_name")
    )

    if not username:
        logger.warning("[TikAPI] No username found in creator_data — skipping aesthetic enrichment.")
        return {"recent_videos": []}

    logger.info("[TikAPI] Fetching top videos for creator username=%s", username)
    product_title = state.get("product_title", "")
    recent_videos = []
    if username:
        recent_videos = TikApiService.enrich_creator(username, product_title=product_title)
    logger.info("[TikAPI] Got %d videos for username=%s", len(recent_videos), username)
    return {"recent_videos": recent_videos}


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

def commerce_evaluation_node(state: SREvaluationState) -> dict:
    """Stage 2: Gemini compatibility analysis — uses strictly standard TikTok Shop Commerce data."""
    creator = state.get("creator_data", {})
    product = state.get("product_data", {})

    creator_open_id = creator.get("creator_open_id")
    product_id = product.get("id")
    access_token = state.get("access_token")
    shop_cipher = state.get("shop_cipher")

    rich_creator_dict = {}
    rich_product_dict = {}

    if access_token:
        if creator_open_id:
            res_c = TikTokCreatorService.get_creator_detail(access_token, shop_cipher, creator_open_id)
            if res_c and isinstance(res_c, dict) and "data" in res_c:
                # The official API nests creator details inside data.creator
                rich_creator_dict = res_c.get("data", {}).get("creator") or res_c.get("data", {})
                logger.info("[Phase 2] Fetched rich TikTok affiliate creator profile for creator_id=%s", creator_open_id)
            else:
                logger.warning("[Phase 2] Failed to fetch TikTok affiliate creator profile for creator_id=%s", creator_open_id)

        if product_id:
            res_p = TikTokProductService.get_product_by_id(access_token, shop_cipher, product_id)
            if res_p and isinstance(res_p, dict) and "data" in res_p:
                rich_product_dict = res_p.get("data", {})
                logger.info("[Phase 2] Fetched rich product detail for product_id=%s", product_id)
            else:
                logger.warning("[Phase 2] Failed to fetch rich product detail for product_id=%s", product_id)

    llm = ChatVertexAI(
        model_name=settings.vertex_model,
        project=settings.gcp_project,
        location="us-central1",
        temperature=0,
    )
    structured_llm = llm.with_structured_output(CommerceScoreResult)

    prompt_str = CREATOR_EVALUATION_PROMPT.format(
        product_title=state.get("product_title"),
        tier=state.get("tier"),
        product_json=json.dumps(_sanitize_product(rich_product_dict), indent=2),
        creator_json=json.dumps(rich_creator_dict, indent=2),  # Sending full affiliate payload
    )

    res = structured_llm.invoke(prompt_str)

    return {
        "commerce_score": res.score,
        "commerce_reasoning": res.reasoning,
        "compatibility_status": "PROCESSED",
        "rich_creator_detail": rich_creator_dict,
        "rich_product_detail": rich_product_dict,
        "product_description": rich_product_dict.get("description"),
    }


def aesthetic_evaluation_node(state: SREvaluationState) -> dict:
    """Stage 3: Gemini aesthetic integration — uses TikAPI video metadata."""
    recent_videos = state.get("recent_videos") or []
    recent_videos_json = json.dumps(recent_videos, indent=2) if recent_videos else "[]"
    
    llm = ChatVertexAI(
        model_name=settings.vertex_model,
        project=settings.gcp_project,
        location="us-central1",
        temperature=0,
    )
    structured_llm = llm.with_structured_output(AestheticScoreResult)

    prompt_str = AESTHETIC_EVALUATION_PROMPT.format(
        product_title=state.get("product_title"),
        product_description=state.get("product_description") or "No description available.",
        tier=state.get("tier"),
        recent_videos_json=json.dumps(_sanitize_video(recent_videos), indent=2),
    )
    
    res = structured_llm.invoke(prompt_str)

    return {
        "aesthetic_score": res.aesthetic_score,
        "aesthetic_reasoning": res.reasoning,
        "top_3_video_urls": res.top_3_video_urls,
    }


def decision_node(state: SREvaluationState) -> dict:
    """Makes a final ACCEPT/REJECT decision based on Phase 2 AND Phase 3 outputs."""
    filters_passed = state.get("filters_passed", False)
    val_reason = state.get("validation_reason", "Failed validation.")
    tier = state.get("tier", "UNKNOWN")

    # 1. Did it fail Stage 1 logic immediately?
    if not filters_passed:
         return {
             "final_decision": "REJECT",
             "decision_reason": f"[Phase 1 Filter Failed] {val_reason}\n\nProduct Category: {tier}",
             "compatibility_status": "SKIPPED"
         }

    # 2. Passed Stage 1, so both Phase 2 (Commerce) and Phase 3 (Aesthetic) ran.
    c_score = state.get("commerce_score", 0)
    a_score = state.get("aesthetic_score", 0)
    threshold = state.get("threshold", 70)
    
    avg_score = (c_score + a_score) / 2
    
    c_reasoning = state.get("commerce_reasoning", "No reasoning provided.")
    a_reasoning = state.get("aesthetic_reasoning", "No reasoning provided.")
    top_videos = state.get("top_3_video_urls", [])

    video_links_str = "\n".join([f"- {url}" for url in top_videos]) if top_videos else "No matching videos found."

    combined_reasoning = (
        f"profile_score: {c_score}/100\n{c_reasoning}\n\n"
        f"aesthetic_score: {a_score}/100\n{a_reasoning}\n\n"
        f"Top Evidence Videos:\n{video_links_str}\n\n"
        f"Product Category: {tier}"
    )

    if avg_score >= threshold:
        return {
            "final_decision": "ACCEPT",
            "decision_reason": combined_reasoning
        }
        
    return {
        "final_decision": "POTENTIAL_ACCEPT",
        "decision_reason": combined_reasoning
    }

def route_after_validation(state: SREvaluationState) -> str:
    if state.get("final_decision") == "ERROR":
        return "end"

    filters_passed = state.get("filters_passed")
    tier = state.get("tier", "UNKNOWN")

    if tier in ("TIER_1", "TIER_2", "TIER_5", "UNKNOWN"):
        return "flag_internal"

    if filters_passed is False:
        return "decision"

    # Passed Phase 1 — go to Phase 2 (Commerce)
    return "commerce_evaluation"
