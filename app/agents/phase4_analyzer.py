"""
Phase 4: Visual Brand Safety Analysis via Gemini 2.5 Flash video understanding.

Downloads top video(s) from TikAPI CDN links and feeds them directly to Gemini
alongside the client-defined product rubric for deep visual evaluation.
"""
import logging
import tempfile
import os
import requests
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from pydantic import BaseModel, Field
from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.agents.rubrics import format_rubric_for_prompt

logger = logging.getLogger(__name__)


class Phase4Result(BaseModel):
    visual_score: int = Field(description="Score 0-100 based on the client rubric criteria.")
    reasoning: str = Field(description="Detailed explanation of how the creator's videos match or miss the rubric.")
    matched_patterns: list[str] = Field(description="List of client patterns clearly observed in the videos.")
    missing_patterns: list[str] = Field(description="List of client patterns NOT observed in the videos.")


PHASE4_PROMPT_TEMPLATE = """You are a TikTok creator evaluation specialist performing a deep video audit.

PRODUCT BEING EVALUATED: {product_title}

{rubric}

You are watching {video_count} TikTok video(s) from creator @{creator_username}.

YOUR TASK:
1. Watch each video carefully. Listen to what the creator says. Observe the visuals — skin texture, filming angles, environment, editing style, and how they interact with their audience.
2. Score the creator 0-100 based on how well they match the CLIENT-DEFINED patterns and qualities above.
   - 80-100: Strong match. Creator clearly demonstrates most patterns and qualities.
   - 50-79: Moderate match. Creator shows some patterns but lacks key qualities.
   - 0-49: Poor match. Creator's video style does not align with this product's requirements.
3. List exactly which client patterns you observed (matched_patterns) and which were absent (missing_patterns).
4. Write a detailed reasoning paragraph explaining your score with specific observations from the videos.

Be specific. Reference actual visual moments, spoken words, or editing patterns you observed. Do not be vague.
"""


def _download_with_ytdlp(web_url: str, index: int) -> str | None:
    """
    Primary download method: uses yt-dlp Python API to download TikTok videos.
    yt-dlp handles TikTok's geo-restricted CDN routing far better than direct requests.
    """
    try:
        import yt_dlp

        tmp_path = tempfile.mktemp(suffix=f"_v{index}.mp4")

        ydl_opts = {
            "outtmpl": tmp_path,
            "format": "mp4/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "merge_output_format": "mp4",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([web_url])

        # yt-dlp may add extension — search for the actual file
        actual_path = tmp_path
        if not os.path.exists(actual_path):
            actual_path = tmp_path + ".mp4"
        if not os.path.exists(actual_path):
            logger.warning("[Phase4] yt-dlp ran but output file not found at %s", tmp_path)
            return None

        size_mb = os.path.getsize(actual_path) / (1024 * 1024)
        print(f"[Phase4] ✅ yt-dlp downloaded video {index} → {size_mb:.1f} MB")
        return actual_path

    except Exception as e:
        logger.warning("[Phase4] yt-dlp failed for video %d (%s): %s", index, web_url, e)
        return None


def _download_video_with_tikapi_sdk(video_id: str, index: int) -> str | None:
    """Secondary: TikAPI SDK save_video (works when CDN is not geo-blocked)."""
    try:
        from tikapi import TikAPI
        api = TikAPI(settings.tikapi_key)
        response = api.public.video(id=video_id)
        data = response.json()
        download_addr = (
            data.get("itemInfo", {}).get("itemStruct", {}).get("video", {}).get("downloadAddr")
            or data.get("itemInfo", {}).get("itemStruct", {}).get("video", {}).get("playAddr")
        )
        if not download_addr:
            return None
        tmp_path = tempfile.mktemp(suffix=f"_v{index}.mp4")
        response.save_video(download_addr, tmp_path)
        if os.path.exists(tmp_path):
            size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
            print(f"[Phase4]  TikAPI SDK downloaded video {index} → {size_mb:.1f} MB")
            return tmp_path
    except Exception as e:
        logger.warning("[Phase4] TikAPI SDK failed for video_id=%s: %s", video_id, e)
    return None


def _download_video_raw_fallback(url: str, index: int) -> str | None:
    """Last resort: raw CDN request with browser-like headers."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
            "Referer": "https://www.tiktok.com/",
        }
        resp = requests.get(url, headers=headers, stream=True, timeout=45)
        resp.raise_for_status()
        tmp_path = tempfile.mktemp(suffix=f"_v{index}.mp4")
        with open(tmp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=1024 * 512):
                if chunk:
                    f.write(chunk)
        size_mb = os.path.getsize(tmp_path) / (1024 * 1024)
        print(f"[Phase4]   Raw CDN fallback downloaded video {index} → {size_mb:.1f} MB")
        return tmp_path
    except Exception as e:
        logger.warning("[Phase4] Raw CDN fallback failed for video %d: %s", index, e)
    return None


def run_phase4_analysis(
    product_title: str,
    creator_username: str,
    video_ids: list[str],
    web_urls: list[str] | None = None,        # TikTok web URLs for yt-dlp
    play_url_fallbacks: list[str] | None = None,  # Raw CDN URLs as last resort
) -> dict:
    """
    Download videos via yt-dlp (primary) → TikAPI SDK → raw CDN fallback,
    then send to Gemini 2.5 for rubric-based visual evaluation.
    """
    if not video_ids and not web_urls:
        return {
            "visual_score": None,
            "reasoning": "No video IDs provided for Phase 4 analysis.",
            "matched_patterns": [],
            "missing_patterns": [],
        }

    ids = video_ids or []
    urls = web_urls or []
    fallbacks = play_url_fallbacks or []
    rubric_str = format_rubric_for_prompt(product_title)
    temp_files = []
    video_parts = []

    for i in range(min(3, max(len(ids), len(urls)))):
        vid_id = ids[i] if i < len(ids) else None
        web_url = urls[i] if i < len(urls) else None
        fallback_url = fallbacks[i] if i < len(fallbacks) else None

        path = None

        # 1. yt-dlp via TikTok web URL (handles CDN geo-routing best)
        if web_url:
            path = _download_with_ytdlp(web_url, i + 1)

        # 2. TikAPI SDK (works when CDN is accessible)
        if not path and vid_id:
            print(f"[Phase4] yt-dlp failed for video {i+1}, trying TikAPI SDK...")
            path = _download_video_with_tikapi_sdk(vid_id, i + 1)

        # 3. Raw CDN URL (last resort)
        if not path and fallback_url:
            print(f"[Phase4] Trying raw CDN as last resort for video {i+1}...")
            path = _download_video_raw_fallback(fallback_url, i + 1)

        if not path:
            logger.warning("[Phase4] All download methods failed for video %d — skipping.", i + 1)
            continue

        temp_files.append(path)
        with open(path, "rb") as f:
            video_data = f.read()
        video_parts.append(Part.from_data(data=video_data, mime_type="video/mp4"))

    if not video_parts:
        return {
            "visual_score": None,
            "reasoning": (
                "Phase 4 video download failed. TikTok's CDN (v16-webapp-prime.tiktok.com) "
                "is geo-restricted from this server location. "
                "This will work correctly when deployed to a US-region cloud server (e.g. Cloud Run us-central1)."
            ),
            "matched_patterns": [],
            "missing_patterns": [],
            "videos_downloaded": 0,
        }

    prompt_text = PHASE4_PROMPT_TEMPLATE.format(
        product_title=product_title,
        rubric=rubric_str,
        video_count=len(video_parts),
        creator_username=creator_username,
    )

    try:
        vertexai.init(project=settings.gcp_project, location="us-central1")
        model = GenerativeModel(settings.vertex_model)

        contents = video_parts + [Part.from_text(prompt_text)]
        response = model.generate_content(
            contents,
            generation_config={"temperature": 0},
        )
        raw_text = response.text

        # Parse structured output using LangChain wrapper
        structured_llm = ChatGoogleGenerativeAI(
            model=settings.vertex_model,
            project=settings.gcp_project,
            location="us-central1",
            temperature=0,
            vertexai=True
        ).with_structured_output(Phase4Result)
        
        parse_prompt = f"""Based on the following video analysis result, extract structured data.

VIDEO ANALYSIS:
{raw_text}

PRODUCT: {product_title}
CREATOR: @{creator_username}
{rubric_str}
"""
        result: Phase4Result = structured_llm.invoke(parse_prompt)

        return {
            "visual_score": result.visual_score,
            "reasoning": result.reasoning,
            "matched_patterns": result.matched_patterns,
            "missing_patterns": result.missing_patterns,
            "videos_downloaded": len(video_parts),
        }

    except Exception as e:
        logger.error("[Phase4] Gemini video analysis failed: %s", e)
        return {
            "visual_score": 0,
            "reasoning": f"Phase 4 analysis failed: {str(e)}",
            "matched_patterns": [],
            "missing_patterns": [],
            "videos_downloaded": len(video_parts),
        }
    finally:
        # Clean up temp files
        for path in temp_files:
            try:
                os.unlink(path)
            except Exception:
                pass
