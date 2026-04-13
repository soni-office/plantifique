import json
import logging
import os

from pydantic import BaseModel, Field
from langchain_google_vertexai import ChatVertexAI

from app.agents.tools import fetch_sample_from_db, resolve_tier
from app.agents.sample_analyzer.state import SREvaluationState
from app.agents.sample_analyzer.prompts import CREATOR_EVALUATION_PROMPT
from app.core.config import settings
from app.clients.tiktok.creator_client import TikTokCreatorClient
from app.clients.tiktok.product_client import TikTokProductClient
from app.cache import cache, keys, ttl

logger = logging.getLogger(__name__)

class ScoreResult(BaseModel):
    """Pydantic model to enforce structured JSON output from Vertex AI."""
    score: int = Field(description="Score out of 100 representing creator-product fit")
    reasoning: str = Field(description="Brief explanation of the score")

def fetch_data_node(state: SREvaluationState) -> dict:
    """
    Phase 0: fetch sample from DB, resolve tier, and — for any tier that requires
    threshold checks — fetch the rich creator detail from TikTok immediately so
    Phase 1 (validation_node) works with real, up-to-date metrics.

    post_rate is extracted from the rich creator detail as:
        raw_post_rate / 100  → actual percentage
    (TikTok stores post_rate as a raw integer, e.g. 7200 → 72 %)
    """
    sample_id = state["sample_request_id"]

    sample = fetch_sample_from_db(sample_id)
    if not sample:
        return {
            "tier": "UNKNOWN",
            "final_decision": "ERROR",
            "decision_reason": f"Sample request '{sample_id}' not found in DB.",
        }

    creator = sample.get("creator", {})
    product = sample.get("product", {})
    username = creator.get("username", "")
    product_id = product.get("id", "")
    product_title = product.get("title", "")
    org_id = sample.get("org_id", "")
    creator_open_id = creator.get("creator_open_id", "")

    tier, thresholds = resolve_tier(org_id=org_id, username=username, product_id=product_id)

    # Fetch rich creator detail for any tier that runs threshold checks.
    # TIER_1 / TIER_2 skip validation entirely so no need to fetch there.
    rich_creator_data = {}
    post_rate = 0.0
    access_token = state.get("access_token")
    shop_cipher_val = state.get("shop_cipher")

    if tier in ("TIER_3", "TIER_4", "TIER_5") and access_token and creator_open_id:
        res_c = cache.cache_or_fetch(
            keys.creator_detail(org_id, creator_open_id),
            ttl.CREATOR_DETAIL,
            lambda: TikTokCreatorClient.get_detail(
                access_token, shop_cipher_val, creator_open_id
            ),
        )
        if res_c and isinstance(res_c, dict) and "data" in res_c:
            rich_creator_data = res_c.get("data", {}).get("creator", {})
            # TikTok returns post_rate as a raw integer (e.g. 7200); divide by 100 → 72 %
            raw_pr = rich_creator_data.get("post_rate") or 0
            post_rate = float(raw_pr) / 100
            logger.info(
                "Rich creator detail fetched creator_open_id=%s post_rate_raw=%s post_rate_pct=%.2f",
                creator_open_id, raw_pr, post_rate,
            )
        else:
            logger.warning(
                "Could not fetch rich creator detail for %s — threshold check will use sample data",
                creator_open_id,
            )

    return {
        "org_id": org_id,
        "tier": tier,
        "creator_data": creator,
        "rich_creator_data": rich_creator_data,
        "product_data": product,
        "product_title": product_title,
        "thresholds": thresholds,
        "post_rate": post_rate,
    }

def _extract_creator_metrics(creator: dict) -> tuple[float, int, int, int]:
    """
    Extract the four metric values from a creator dict.
    Handles both the rich creator detail structure and the flat sample creator structure.

    Returns: (gmv_30d, follower_count, content_count, ec_video_views)
    """
    # GMV: rich detail may return gmv_30d or gmv, both as {"amount": "...", "currency": "..."}
    gmv_obj = creator.get("gmv_30d") or creator.get("gmv") or {}
    if isinstance(gmv_obj, dict):
        gmv = float(gmv_obj.get("amount") or 0)
    else:
        gmv = float(gmv_obj or 0)

    followers = int(creator.get("follower_count") or 0)

    # Content count: try rich field first, fall back to flat field
    content_count = int(
        creator.get("content_count_30d")
        or creator.get("content_count")
        or 0
    )

    # EC video views: try plural then singular (API inconsistency)
    ec_video_views = int(
        creator.get("ec_video_views")
        or creator.get("ec_video_view")
        or 0
    )

    return gmv, followers, content_count, ec_video_views


def _check_thresholds(creator: dict, thresholds: dict, post_rate: float) -> tuple[bool, str]:
    """
    Apply threshold checks against the creator dict (preferably rich creator detail).
    Any threshold key set to None is skipped.
    Returns (passed: bool, reason: str).
    """
    gmv, followers, content_count, ec_video_views = _extract_creator_metrics(creator)

    checks = [
        ("min_last_30_days_gmv",  gmv,            f"GMV ${gmv:,.2f}",                    "needs ${val:,.2f}"),
        ("min_follower_count",    followers,       f"Followers {followers:,}",             "needs {val:,}"),
        ("min_post_rate",         post_rate,       f"Post rate {post_rate:.1f}%",          "needs {val}%"),
        ("min_content_count",     content_count,   f"Content count {content_count}",       "needs {val}"),
        ("min_ec_video_views",    ec_video_views,  f"EC video views {ec_video_views:,}",   "needs {val:,}"),
    ]

    for key, actual, actual_label, need_template in checks:
        minimum = thresholds.get(key)
        if minimum is None:
            continue   # threshold not configured → skip
        if actual < minimum:
            need_str = need_template.format(val=minimum)
            return False, f"Failed {key}: {actual_label}, {need_str}."

    return True, "Passed all configured threshold checks."


def validation_node(state: SREvaluationState) -> dict:
    """
    Stage 1: Threshold validation.

    Uses rich creator detail (fetched in fetch_data_node) for accurate metrics.
    Falls back to the shallow sample creator data if the detail fetch failed.

    TIER_1 / TIER_2  → skip entirely (exception/retainer lists, internal processing)
    TIER_3 / TIER_4  → check per-product thresholds; fail → REJECT, pass → proceed to LLM
    TIER_5           → check global thresholds; fail or pass → FLAG_INTERNAL (no LLM)
    UNKNOWN          → FLAG_INTERNAL immediately
    """
    # Prefer the rich detail; fall back to shallow sample data
    rich_creator = state.get("rich_creator_data") or {}
    creator = rich_creator if rich_creator else (state.get("creator_data") or {})
    using_rich = bool(rich_creator)

    thresholds = state.get("thresholds") or {}
    tier = state.get("tier", "UNKNOWN")
    post_rate = state.get("post_rate", 0.0)

    gmv, followers, _, _ = _extract_creator_metrics(creator)
    logger.info(
        "Validation tier=%s username=%s followers=%s gmv=%.2f post_rate=%.1f%% using_rich_data=%s",
        tier,
        (rich_creator or state.get("creator_data", {})).get("username"),
        followers,
        gmv,
        post_rate,
        using_rich,
    )

    if tier in ("TIER_1", "TIER_2", "UNKNOWN"):
        return {
            "filters_passed": None,
            "validation_reason": f"{tier} — routed to internal team, no threshold checks.",
        }

    passed, reason = _check_thresholds(creator, thresholds, post_rate)

    if tier in ("TIER_3", "TIER_4"):
        return {"filters_passed": passed, "validation_reason": reason}

    # TIER_5: always goes to FLAG_INTERNAL, but we record whether thresholds passed
    return {
        "filters_passed": passed,
        "validation_reason": f"TIER_5 — {reason}",
    }

def flag_internal_node(state: SREvaluationState) -> dict:
    """Flags requests that bypass the AI for internal human-led review."""
    tier = state.get("tier", "UNKNOWN")
    val_reason = state.get("validation_reason", "")
    reasons = {
        "TIER_1": "Retainer creator (TIER_1) — handled by internal team, no agentic processing.",
        "TIER_2": "Exception list creator (TIER_2) — requires manual internal review (Discord/DMs).",
        "TIER_5": f"Not in Tier 3/4 product list (TIER_5) — standard metric filter applied. {val_reason}",
        "UNKNOWN": "Tier could not be determined — flagged for manual review.",
    }
    return {
        "final_decision": "FLAG_INTERNAL",
        "decision_reason": reasons.get(tier, f"Flagged for internal review. {val_reason}"),
    }

def llm_score_node(state: SREvaluationState) -> dict:
    """Stage 2: Invokes Gemini for a rich Profile/Product Compatibility Check"""
    creator = state.get("creator_data", {})
    product = state.get("product_data", {})
    
    creator_open_id = creator.get("creator_open_id")
    product_id = product.get("id")
    access_token = state.get("access_token")
    shop_cipher = state.get("shop_cipher")
    
    org_id = state.get("org_id", "")

    # Creator detail was already fetched (and cached) in fetch_data_node — reuse it.
    rich_creator_dict = state.get("rich_creator_data") or {}
    rich_product_dict = {}

    if access_token:
        # 1. Creator detail: only fetch if fetch_data_node couldn't get it
        #    (e.g. TIER_1/2 skip it, or the API failed). Cache hit is instant anyway.
        if not rich_creator_dict and creator_open_id:
            res_c = cache.cache_or_fetch(
                keys.creator_detail(org_id, creator_open_id),
                ttl.CREATOR_DETAIL,
                lambda: TikTokCreatorClient.get_detail(access_token, shop_cipher, creator_open_id),
            )
            if res_c and isinstance(res_c, dict) and "data" in res_c:
                rich_creator_dict = res_c.get("data", {}).get("creator", {})
            else:
                logger.warning("Failed to fetch rich creator detail for %s", creator_open_id)

        # 2. Fetch rich product detail (cached)
        if product_id:
            res_p = cache.cache_or_fetch(
                keys.product_detail(org_id, product_id),
                ttl.PRODUCT_DETAIL,
                lambda: TikTokProductClient.get_by_id(access_token, shop_cipher, product_id),
            )
            if res_p and isinstance(res_p, dict) and "data" in res_p:
                rich_product_dict = res_p.get("data", {})
            else:
                logger.warning("Failed to fetch rich product detail for %s", product_id)
        
    # --- RAG context retrieval (optional) ---
    rag_context_section = ""
    if settings.want_to_use_rag:
        from app.rag.store import query_rag
        product_title = state.get("product_title", "")
        tier = state.get("tier", "")
        rag_query = f"{product_title} {tier} creator evaluation criteria aesthetic standards approval policy"
        raw_context = query_rag(rag_query, n_results=3)
        if raw_context:
            rag_context_section = (
                "### BRAND OPERATIONAL GUIDELINES (Retrieved from Policy):\n"
                f"{raw_context}\n"
                "---\n\n"
            )
            logger.info("[RAG] Injected %d chars of policy context into prompt", len(raw_context))
        else:
            logger.info("[RAG] No context retrieved — proceeding without RAG")
    else:
        logger.debug("[RAG] Disabled (WANT_TO_USE_RAG=false)")

    llm = ChatVertexAI(
        model_name=settings.vertex_model,
        project="tiktok-ai-agent-488417",
        location="us-central1",
        temperature=0,
    )
    structured_llm = llm.with_structured_output(ScoreResult)

    prompt_str = CREATOR_EVALUATION_PROMPT.format(
        rag_context=rag_context_section,
        product_title=state.get("product_title"),
        tier=state.get("tier"),
        product_json=json.dumps(rich_product_dict, indent=2),
        creator_json=json.dumps(rich_creator_dict, indent=2),
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
    """Routing after validation node."""
    if state.get("final_decision") == "ERROR":
        return "end"

    tier = state.get("tier", "UNKNOWN")
    filters_passed = state.get("filters_passed")

    # Tier 1/2: exception/retainer lists → internal team, no LLM
    if tier in ("TIER_1", "TIER_2", "UNKNOWN"):
        return "flag_internal"

    # Tier 5: standard metric filter applied → always flag internal, no LLM
    if tier == "TIER_5":
        return "flag_internal"

    # Tier 3/4: threshold failed → reject, no LLM
    if filters_passed is False:
        return "decision"

    # Tier 3/4: threshold passed → LLM scoring
    return "llm_score"
