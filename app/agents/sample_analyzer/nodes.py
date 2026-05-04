import json
import logging
import os

from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

from app.agents.tools import fetch_sample_from_db, resolve_tier
from app.agents.sample_analyzer.state import SREvaluationState
from app.agents.sample_analyzer.prompts import (
    CREATOR_EVALUATION_PROMPT,
    AESTHETIC_EVALUATION_PROMPT
)
from app.core.config import settings
from app.clients.tiktok.creator_client import TikTokCreatorClient
from app.clients.tiktok.product_client import TikTokProductClient
from app.cache import cache, keys, ttl
from app.services.tikapi_service import tikapi_service
from app.agents.phase4_analyzer import run_phase4_analysis

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
    """
    Phase 0: fetch sample from DB, resolve tier, and — for any tier that requires
    threshold checks — fetch the rich creator detail from TikTok immediately so
    Phase 1 (validation_node) works with real, up-to-date metrics.
    Phase 2 and Phase 3 performs the aesthetic evaluation of the creator as per the product niche.

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

def _extract_gmv(creator: dict) -> float | None:
    """
    Extract GMV from a creator dict, returning None when the creator has hidden
    their data (field absent from the API response) rather than conflating it with $0.

    TikTok omits the gmv/gmv_30d field entirely when a creator has not granted
    data-sharing permission. An absent field → None (hidden).
    A present field with amount "0" → 0.0 (genuinely no sales).

    Also checks gmv_range as a secondary signal: if the range is present, the
    creator has some GMV activity even though the exact figure is hidden.
    """
    gmv_30d = creator.get("gmv_30d")
    gmv     = creator.get("gmv")
    gmv_obj = gmv_30d or gmv  # None when both are absent

    if gmv_obj is None:
        # Field missing → creator has hidden their GMV data.
        # gmv_range being present is a secondary signal they have some activity,
        # but either way we return None so the threshold check is skipped.
        return None

    if isinstance(gmv_obj, dict):
        amount = gmv_obj.get("amount")
        if amount is None:
            # Nested amount absent inside the object → also treat as hidden
            return None
        return float(amount)

    return float(gmv_obj)


def _extract_creator_metrics(creator: dict) -> tuple[float | None, int, int, int]:
    """
    Extract the four metric values from a creator dict.
    Handles both the rich creator detail structure and the flat sample creator structure.

    Returns: (gmv, follower_count, content_count, ec_video_views)
    gmv is None when the creator has hidden their data — callers must handle this.
    """
    gmv = _extract_gmv(creator)

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

    Rules:
    - Threshold key not configured (None in thresholds dict) → skip check
    - Metric value is None (creator hid the data) → skip that check, note it
    - Metric value present and below minimum → FAIL
    Returns (passed: bool, reason: str).
    """
    gmv, followers, content_count, ec_video_views = _extract_creator_metrics(creator)

    gmv_label = f"GMV ${gmv:,.2f}" if gmv is not None else "GMV hidden by creator"

    checks = [
        ("min_last_30_days_gmv",  gmv,            gmv_label,                             "needs ${val:,.2f}"),
        ("min_follower_count",    followers,       f"Followers {followers:,}",             "needs {val:,}"),
        ("min_post_rate",         post_rate,       f"Post rate {post_rate:.1f}%",          "needs {val}%"),
        ("min_content_count",     content_count,   f"Content count {content_count}",       "needs {val}"),
        ("min_ec_video_views",    ec_video_views,  f"EC video views {ec_video_views:,}",   "needs {val:,}"),
    ]

    skipped_hidden = []

    for key, actual, actual_label, need_template in checks:
        minimum = thresholds.get(key)
        if minimum is None:
            continue  # threshold not configured → skip

        if actual is None:
            # Creator has hidden this metric — give benefit of the doubt, do not fail
            skipped_hidden.append(actual_label)
            continue

        if actual < minimum:
            need_str = need_template.format(val=minimum)
            return False, f"Failed {key}: {actual_label}, {need_str}."

    if skipped_hidden:
        hidden_note = f" (skipped hidden metrics: {', '.join(skipped_hidden)})"
    else:
        hidden_note = ""

    return True, f"Passed all configured threshold checks.{hidden_note}"


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

    logger.info(
        "Validation tier=%s username=%s - using_rich_data=%s",
        tier,
        (rich_creator or state.get("creator_data", {})).get("username"),
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

def fetch_aesthetic_data_node(state: SREvaluationState) -> dict:
    """
    Stage 1.5: Fetch the creator's top 10 public TikTok videos via TikAPI.

    """
    creator = state.get("creator_data") or {}
    username = (
        creator.get("username")
        or creator.get("nickname")
        or creator.get("creator_open_id")
    )

    if not username:
        logger.warning("[TikAPI] No username found in creator_data — skipping aesthetic enrichment.")
        return {"recent_videos": []}

    logger.info("[TikAPI] Fetching top videos for creator username=%s", username)
    product_title = state.get("product_title", "")
    try:
        recent_videos = tikapi_service.enrich_creator(username, product_title=product_title)
    except Exception as e:
        logger.warning("[TikAPI] enrich_creator failed for username=%s: %s", username, e)
        recent_videos = []
    logger.info("[TikAPI] Got %d videos for username=%s", len(recent_videos), username)
    return {"recent_videos": recent_videos}


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

def roi_check_node(state: SREvaluationState) -> dict:
    """
    Stage 1b: ROI Validation Gate (Tier 4 Only)

    Ensures the creator has previously 'COMPLETED' a Plantifique sample
    (which proves they generate sales value). Uses the Seller Search API.
    """
    tier = state.get("tier", "UNKNOWN")

    if tier != "TIER_4":
        logger.info("[ROI Check] Skipped — tier=%s is not TIER_4", tier)
        return {"roi_passed": None, "roi_reason": f"ROI check not applicable for {tier}."}

    creator = state.get("creator_data", {}) or {}
    username = creator.get("username")
    access_token = state.get("access_token")
    shop_cipher = state.get("shop_cipher")

    if not username or not access_token:
        logger.warning("[ROI Check] Failed — Missing username or access_token")
        return {
            "roi_passed": False,
            "roi_reason": "[Tier 4 ROI Gate] Failed (Missing username or token)",
        }

    logger.info("[ROI Check] Running Tier 4 ROI gate for username=%s", username)

    try:
        from app.clients.tiktok.sample_client import TikTokSampleClient
        res = TikTokSampleClient.search(
            access_token=access_token,
            shop_cipher=shop_cipher,
            status="COMPLETED",
            username=username
        )
        applications = res.get("data", {}).get("sample_applications", [])
        if len(applications) > 0:
            reason = f"[Tier 4 ROI Gate Passed] Creator '{username}' has {len(applications)} 'COMPLETED' sample(s) with Plantifique."
            logger.info("[ROI Check] PASSED for username=%s", username)
            return {"roi_passed": True, "roi_reason": reason}
        else:
            reason = f"[Tier 4 ROI Gate Failed] Creator '{username}' has zero 'COMPLETED' samples with Plantifique."
            logger.info("[ROI Check] FAILED for username=%s (zero returned)", username)
            return {"roi_passed": False, "roi_reason": reason}
    except Exception as e:
        logger.error("[ROI Check] API Error for username=%s: %s", username, e)
        return {
            "roi_passed": False,
            "roi_reason": f"[Tier 4 ROI Gate Error] Unable to verify history: {str(e)}"
        }


def route_after_roi(state: SREvaluationState) -> str:
    """Routing after roi_check_node. False -> decision, else -> commerce_evaluation"""
    if state.get("roi_passed") is False:
        return "decision"
    return "commerce_evaluation"


def commerce_evaluation_node(state: SREvaluationState) -> dict:
    """Stage 2: Gemini compatibility analysis — uses strictly standard TikTok Shop Commerce data."""
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
                # The official API nests creator details inside data.creator
                data_obj = res_c.get("data")
                rich_creator_dict = data_obj.get("creator") or data_obj
                logger.info("[Phase 2] Fetched rich TikTok affiliate creator profile for creator_id=%s", creator_open_id)
            else:
                logger.warning("[Phase 2] Failed to fetch TikTok affiliate creator profile for creator_id=%s", creator_open_id)

        # 2. Fetch rich product detail (cached)
        if product_id:
            res_p = cache.cache_or_fetch(
                keys.product_detail(org_id, product_id),
                ttl.PRODUCT_DETAIL,
                lambda: TikTokProductClient.get_by_id(access_token, shop_cipher, product_id),
            )
            if res_p and isinstance(res_p, dict) and "data" in res_p:
                rich_product_dict = res_p.get("data", {})
                logger.info("[Phase 2] Fetched rich product detail for product_id=%s", product_id)
            else:
                logger.warning("[Phase 2] Failed to fetch rich product detail for product_id=%s", product_id)
        
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

    llm = ChatGoogleGenerativeAI(
        model=settings.vertex_model,
        project=settings.gcp_project,
        location="us-central1",
        temperature=0,
        vertexai=True
    )
    structured_llm = llm.with_structured_output(CommerceScoreResult)

    prompt_str = CREATOR_EVALUATION_PROMPT.format(
        rag_context=rag_context_section,
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
    
    llm = ChatGoogleGenerativeAI(
        model=settings.vertex_model,
        project=settings.gcp_project,
        location="us-central1",
        temperature=0,
        vertexai=True
    )
    structured_llm = llm.with_structured_output(AestheticScoreResult)

    prompt_str = AESTHETIC_EVALUATION_PROMPT.format(
        product_title=state.get("product_title"),
        product_description=state.get("product_description") or "No description available.",
        tier=state.get("tier"),
        recent_videos_json=recent_videos_json,
    )
    res = structured_llm.invoke(prompt_str)

    return {
        "aesthetic_score": res.aesthetic_score,
        "aesthetic_reasoning": res.reasoning,
        "top_3_video_urls": res.top_3_video_urls,
    }


def visual_evaluation_node(state: SREvaluationState) -> dict:
    """Stage 4: Deep Video Frame & Audio Analysis using yt-dlp & Gemini Flash."""
    product_title = state.get("product_title", "")
    product_id = state.get("product_data", {}).get("id")
    creator = state.get("creator_data", {})
    username = creator.get("username") or creator.get("handle") or creator.get("creator_name") or "Unknown"

    videos = state.get("recent_videos") or []
    top_video_urls = state.get("top_3_video_urls") or []

    top_url_set = set(top_video_urls)
    selected_videos = [
        v for v in videos
        if v.get("web_url") in top_url_set or v.get("play_url") in top_url_set
    ]
    # skipping the visual phase 4 completely if no relvant videos were found i phase 3
    # if not selected_videos:
    #     selected_videos = videos[:3]

    video_ids = [v["video_id"] for v in selected_videos if v.get("video_id")]
    web_urls = [v["web_url"] for v in selected_videos if v.get("web_url")]
    play_url_fallbacks = [v["play_url"] for v in selected_videos if v.get("play_url")]

    if not video_ids:
        return {
            "visual_score": None,
            "visual_reasoning": "Skipped Phase 4: No relevant videos for the product were found in Phase 3 analysis among the recent or trending videos from creator.",
            "matched_patterns": [],
            "missing_patterns": []
        }

    logger.info("[Phase 4] Starting visual analysis for %d videos", len(video_ids))
    try:
        phase4_result = run_phase4_analysis(
            product_id=product_id,
            product_title=product_title,
            creator_username=username,
            video_ids=video_ids,
            web_urls=web_urls,
            play_url_fallbacks=play_url_fallbacks,
            org_id=state.get("org_id") or "default",
        )
    except Exception as e:
        logger.error("[Phase 4] Failed frame analysis: %s", e)
        phase4_result = {"visual_score": None, "reasoning": f"Analysis crashed: {e}"}

    return {
        "visual_score": phase4_result.get("visual_score"),
        "visual_reasoning": phase4_result.get("reasoning"),
        "matched_patterns": phase4_result.get("matched_patterns", []),
        "missing_patterns": phase4_result.get("missing_patterns", [])
    }


def decision_node(state: SREvaluationState) -> dict:
    """Makes a final ACCEPT/REJECT decision based on Phase 2 AND Phase 3 outputs."""
    filters_passed = state.get("filters_passed", False)
    val_reason = state.get("validation_reason", "Failed validation.")
    roi_passed = state.get("roi_passed")
    roi_reason = state.get("roi_reason", "")
    tier = state.get("tier", "UNKNOWN")

    # 1. Did it fail Stage 1 logic immediately?
    if not filters_passed:
         return {
             "final_decision": "REJECT",
             "decision_reason": f"[Phase 1 Filter Failed] {val_reason}\n\nProduct Category: {tier}",
             "compatibility_status": "SKIPPED"
         }

    # 2. Did it fail Stage 1b ROI Gate? (Tier 4 only)
    if roi_passed is False:
         return {
             "final_decision": "REJECT",
             "decision_reason": f"{roi_reason}\n\nProduct Category: {tier}",
             "compatibility_status": "SKIPPED"
         }

    # 3. Passed Stage 1 and 1b — evaluate Phase 2 (Commerce) score
    c_score = state.get("commerce_score", 0)
    c_reasoning = state.get("commerce_reasoning", "No reasoning provided.")
    threshold = state.get("threshold", 70)

    # If aesthetic phases were skipped (commerce gate), reject on commerce score alone
    aesthetic_skipped = state.get("aesthetic_score") is None
    if aesthetic_skipped:
        combined_reasoning = (
            f"commerce_score: {c_score}/100\n\n"
            f"Aesthetic & visual phases skipped — commerce score {c_score} fell below the "
            f"minimum threshold (45) required to proceed.\n\n"
            f"Commerce reasoning: {c_reasoning}\n\n"
            f"Product Category: {tier}"
        )
        return {
            "final_decision": "REJECT",
            "decision_reason": combined_reasoning,
        }

    a_score = state.get("aesthetic_score", 0)
    

    a_reasoning = state.get("aesthetic_reasoning", "No reasoning provided.")
    top_videos = state.get("top_3_video_urls", [])
    video_links_str = "\n".join([f"- {url}" for url in top_videos]) if top_videos else "No matching videos found."

    combined_reasoning = (
        f"commerce_score: {c_score}/100\n\n"
        f"aesthetic_score: {a_score}/100\n\n"
    )

    v_score = 0
    if state.get("visual_score") is not None:
        v_score = state.get("visual_score")
        combined_reasoning += f"visual_score (Phase 4): {v_score}/100\n\n"

    combined_reasoning += (
        f"Top Evidence Videos:\n{video_links_str}\n\n"
        f"Product Category: {tier}"
    )
    avg_score = (c_score + a_score + v_score) / 3

    if avg_score >= threshold:
        return {
            "final_decision": "ACCEPT",
            "decision_reason": combined_reasoning
        }

    return {
        "final_decision": "POTENTIAL_ACCEPT",
        "decision_reason": combined_reasoning
    }

def route_after_commerce(state: SREvaluationState) -> str:
    """
    Routing after commerce_evaluation_node.

    If commerce_score is below the minimum threshold (default 45) the creator
    already lacks product-market fit — skip the expensive aesthetic + visual
    phases and go straight to a final decision.
    """
    commerce_score = state.get("commerce_score", 0)
    min_commerce_score = 45  # configurable cut-off
    if commerce_score < min_commerce_score:
        logger.info(
            "[Commerce Gate] commerce_score=%d < %d — skipping aesthetic/visual phases",
            commerce_score, min_commerce_score,
        )
        return "decision"
    logger.info(
        "[Commerce Gate] commerce_score=%d >= %d — proceeding to aesthetic evaluation",
        commerce_score, min_commerce_score,
    )
    return "fetch_aesthetic_data"


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

    # Passed Phase 1 — go to ROI check (which auto-skips for non-Tier4, then proceeds to Phase 2)
    return "roi_check"
