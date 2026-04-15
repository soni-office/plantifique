from fastapi import APIRouter, Depends
from pydantic import BaseModel
import json
import logging

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


@router.post("/evaluate-aesthetic")
async def evaluate_aesthetic(
    body: AestheticTestBody,
    user=Depends(get_current_user),
):
    """
    Testing endpoint: runs Phase 3 (Aesthetic) + Phase 4 (Video Analysis) 
    for any product + creator pair without needing a sample request.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI
    from app.agents.sample_analyzer.prompts import AESTHETIC_EVALUATION_PROMPT
    from app.agents.sample_analyzer.nodes import _sanitize_video, AestheticScoreResult
    from app.agents.phase4_analyzer import run_phase4_analysis

    try:
        token_service = TokenService()
        access_token = token_service.get_valid_access_token(user["org_id"])
        res = shop_cipher(user["org_id"])
        if not res or not res.get("data") or not res["data"].get("shops"):
            raise ValueError(f"No shop found associated with org_id {user['org_id']}. Please check TikTok connection. Response: {res}")
            
        cipher = res["data"]["shops"][0]["cipher"]
        # Fetch live product details from TikTok Sandbox
        product_res = TikTokProductClient.get_by_id(access_token, cipher, body.product_id)
        
        product_data = {}
        if product_res and isinstance(product_res, dict):
            product_data = product_res.get("data") or {}
            
        if not product_data:
            # Fallback to mock data if live API fails
            logger.info("[Testing] Product ID %s not found in live API. Attempting mock fallback...", body.product_id)
            from app.mock.sample_mock_data import get_mock_sample_requests
            all_mocks = get_mock_sample_requests()
            for m in all_mocks:
                apps = m.get("data", {}).get("sample_applications", [])
                for a in apps:
                    if a.get("product", {}).get("id") == body.product_id:
                        product_data = a["product"]
                        break
                if product_data: break
        
        product_title = product_data.get("title", product_data.get("product_name", "Unknown Product"))
        product_description = product_data.get("description", "")
        tier = resolve_tier(user['org_id'], body.creator_username , product_id=body.product_id)

        # Phase 3: Fetch creator videos with intelligent playlist routing
        videos = tikapi_service.enrich_creator(username=body.creator_username, product_title=product_title)
        print(f"[Testing] Fetched {len(videos)} videos for {body.creator_username}")

        # Phase 3: Gemini Aesthetic Score
        llm = ChatGoogleGenerativeAI(
            model=settings.vertex_model,
            project=settings.gcp_project,
            location="us-central1",
            temperature=0,
            vertexai=True
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
        print(f"[Testing] Phase 3 complete. Score={phase3_result.aesthetic_score}, Top URLs: {top_video_urls}")

        # Phase 4: Collect video_ids from the top videos Phase 3 selected
        # We resolve download URLs through TikAPI's own endpoint (bypasses CDN cookie requirement)
        top_url_set = set(top_video_urls)
        selected_videos = [
            v for v in videos
            if v.get("web_url") in top_url_set or v.get("play_url") in top_url_set
        ]
        # Fallback: use first 3 videos if Phase 3 URL matching didn't find exact hits
        if not selected_videos:
            selected_videos = videos[:3]

        video_ids = [v["video_id"] for v in selected_videos if v.get("video_id")]
        web_urls = [v["web_url"] for v in selected_videos if v.get("web_url")]
        play_url_fallbacks = [v["play_url"] for v in selected_videos if v.get("play_url")]

        print(f"[Testing] Starting Phase 4 video download for {len(video_ids)} videos (IDs: {video_ids})...")
        phase4_result = run_phase4_analysis(
            product_title=product_title,
            creator_username=body.creator_username,
            video_ids=video_ids,
            web_urls=web_urls,
            play_url_fallbacks=play_url_fallbacks,
        )
        print(f"[Testing] Phase 4 complete. Visual Score={phase4_result.get('visual_score')}")

        return {
            "status": "success",
            "product_title": product_title,
            "tier": tier[0],
            "creator_username": body.creator_username,
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
            # Client rubric used
            "rubric_applied": format_rubric_for_prompt(product_title),
        }

    except Exception as e:
        logger.error("Error in aesthetic testing: %s", e)
        return {"status": "error", "message": str(e)}
