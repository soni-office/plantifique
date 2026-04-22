import asyncio
import json
import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth_session import get_current_user
from app.services.token_service import TokenService
from app.clients.tiktok.product_client import TikTokProductClient
from app.services.tikapi_service import tikapi_service
from app.agents.tools import resolve_tier
from app.agents.rubrics import format_rubric_for_prompt
from app.utils.shop_ciphers import shop_cipher
from app.core.config import settings

router = APIRouter(prefix="/tiktok/testing", tags=["Testing"])
logger = logging.getLogger(__name__)


class AestheticTestBody(BaseModel):
    product_id: str
    creator_username: str


def _run_aesthetic_eval(org_id: str, product_id: str, creator_username: str) -> dict:
    """
    Synchronous implementation of Phase 3 + Phase 4 evaluation.
    Called via run_in_executor so it never blocks the event loop.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    from app.agents.sample_analyzer.prompts import AESTHETIC_EVALUATION_PROMPT
    from app.agents.sample_analyzer.nodes import _sanitize_video, AestheticScoreResult
    from app.agents.phase4_analyzer import run_phase4_analysis

    token_service = TokenService()
    access_token = token_service.get_valid_access_token(org_id)
    res = shop_cipher(org_id)
    if not res or not res.get("data") or not res["data"].get("shops"):
        raise ValueError(
            f"No shop found associated with org_id {org_id}. "
            f"Please check TikTok connection. Response: {res}"
        )

    cipher = res["data"]["shops"][0]["cipher"]

    # Fetch live product details from TikTok
    product_res = TikTokProductClient.get_by_id(access_token, cipher, product_id)
    product_data = {}
    if product_res and isinstance(product_res, dict):
        product_data = product_res.get("data") or {}

    # TODO: rmove fallback to mock data - we don't want it
    if not product_data:
        # Fallback to mock data if live API fails
        logger.info("[Testing] Product ID %s not found in live API. Attempting mock fallback...", product_id)
        from app.mock.sample_mock_data import get_mock_sample_requests
        for m in get_mock_sample_requests():
            for a in m.get("data", {}).get("sample_applications", []):
                if a.get("product", {}).get("id") == product_id:
                    product_data = a["product"]
                    break
            if product_data:
                break

    product_title = product_data.get("title", product_data.get("product_name", "Unknown Product"))
    product_description = product_data.get("description", "")
    tier = resolve_tier(org_id, creator_username, product_id=product_id)

    # Phase 3: fetch creator videos
    videos = tikapi_service.enrich_creator(username=creator_username, product_title=product_title)
    logger.info("[Testing] Fetched %d videos for %s", len(videos), creator_username)

    # Phase 3: Gemini aesthetic score
    llm = ChatGoogleGenerativeAI(
        model=settings.vertex_model,
        project=settings.gcp_project,
        location="us-central1",
        temperature=0,
        vertexai=True,
    )
    structured_llm = llm.with_structured_output(AestheticScoreResult)
    prompt_str = AESTHETIC_EVALUATION_PROMPT.format(
        product_title=product_title,
        product_description=product_description or "No description available.",
        tier=tier,
        recent_videos_json=json.dumps(_sanitize_video(videos), indent=2),
    )
    phase3_result = structured_llm.invoke(prompt_str)
    top_video_urls = phase3_result.top_3_video_urls or []
    logger.info("[Testing] Phase 3 complete. Score=%d top_urls=%s", phase3_result.aesthetic_score, top_video_urls)

    # Phase 4: match top videos and run frame analysis
    top_url_set = set(top_video_urls)
    selected_videos = [
        v for v in videos
        if v.get("web_url") in top_url_set or v.get("play_url") in top_url_set
    ]
    if not selected_videos:
        selected_videos = videos[:3]

    video_ids = [v["video_id"] for v in selected_videos if v.get("video_id")]
    web_urls = [v["web_url"] for v in selected_videos if v.get("web_url")]
    play_url_fallbacks = [v["play_url"] for v in selected_videos if v.get("play_url")]

    logger.info("[Testing] Starting Phase 4 for %d videos (IDs: %s)", len(video_ids), video_ids)
    phase4_result = run_phase4_analysis(
        product_id=product_id,
        product_title=product_title,
        creator_username=creator_username,
        video_ids=video_ids,
        web_urls=web_urls,
        play_url_fallbacks=play_url_fallbacks,
        org_id=org_id,
    )
    logger.info("[Testing] Phase 4 complete. Visual Score=%s", phase4_result.get("visual_score"))

    return {
        "status": "success",
        "product_title": product_title,
        "tier": tier[0],
        "creator_username": creator_username,
        "videos_analyzed": len(videos),
        # Phase 3
        "aesthetic_score": phase3_result.aesthetic_score,
        "aesthetic_reasoning": phase3_result.reasoning,
        "top_3_video_urls": top_video_urls,
        # Phase 4
        "visual_score": phase4_result.get("visual_score"),
        "visual_reasoning": phase4_result.get("reasoning"),
        "matched_patterns": phase4_result.get("matched_patterns", []),
        "missing_patterns": phase4_result.get("missing_patterns", []),
        "videos_downloaded_for_analysis": phase4_result.get("videos_downloaded", 0),
        # Client rubric used for this analysis
        "rubric_applied": format_rubric_for_prompt(product_title),
    }


@router.post("/evaluate-aesthetic")
async def evaluate_aesthetic(
    body: AestheticTestBody,
    user=Depends(get_current_user),
):
    """
    Testing endpoint: runs Phase 3 (Aesthetic) + Phase 4 (Video Analysis)
    for any product + creator pair without needing a sample request.
    Runs entirely in a thread-pool executor — never blocks the event loop.
    """
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(
            None,
            lambda: _run_aesthetic_eval(user["org_id"], body.product_id, body.creator_username),
        )
    except Exception as e:
        logger.error("Error in aesthetic testing: %s", e)
        return {"status": "error", "message": str(e)}
