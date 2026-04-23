"""
Phase 4: Visual Brand Safety Analysis via Gemini 2.5 Flash video understanding.

Downloads top video(s) from TikAPI CDN links, uploads them to GCS, then passes
gs:// URIs to Vertex AI — bypassing the ~10 MB inline request body limit.

GCS bucket lifecycle rule (set once in console): Age = 2 days → Delete.
Videos are also deleted immediately after analysis completes.
"""
import logging
import time
import tempfile
import os
import uuid
import requests
import vertexai
from datetime import date
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
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

IMPORTANT CONTEXT:
- The provided videos may NOT fully represent the creator's overall content niche.
- These videos are a sample (e.g., trending or playlist-based).
- If the videos do not show relevant evidence for the product category, do NOT assume the creator lacks that capability — only evaluate based on visible evidence in these videos.

YOUR TASK:
1. Watch each video carefully. Listen to what the creator says. Observe the visuals — skin texture, filming angles, environment, editing style, and how they interact with their audience.
2. Score the creator 0-100 based on how well they match the CLIENT-DEFINED patterns and qualities above.
   - 80-100: Strong match. Creator clearly demonstrates most patterns and qualities.
   - 50-79: Moderate match. Creator shows some patterns but lacks key qualities.
   - 0-49: Poor match. Creator's video style does not align with this product's requirements OR there is insufficient evidence in the provided videos.
3. List exactly which client patterns you observed (matched_patterns) and which were absent or not evidenced in the provided videos (missing_patterns).
4. Write a detailed reasoning paragraph explaining your score with specific observations from the videos.

IMPORTANT:
- If relevant patterns are not observed, explicitly state that this is due to lack of evidence in the provided videos.
- Do NOT generalize about the creator's overall content beyond what is visible.

Be specific. Reference actual visual moments, spoken words, or editing patterns you observed. Do not be vague.
"""


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def _download_with_ytdlp(web_url: str, index: int) -> str | None:
    """
    Primary download method: uses yt-dlp to download TikTok videos at best quality.
    Videos are uploaded to GCS so there is no inline size limit.
    """
    try:
        import yt_dlp

        tmp_path = tempfile.mktemp(suffix=f"_v{index}.mp4")

        ydl_opts = {
            "outtmpl": tmp_path,
            "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "merge_output_format": "mp4",
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([web_url])

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
            print(f"[Phase4] TikAPI SDK downloaded video {index} → {size_mb:.1f} MB")
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
        print(f"[Phase4] Raw CDN fallback downloaded video {index} → {size_mb:.1f} MB")
        return tmp_path
    except Exception as e:
        logger.warning("[Phase4] Raw CDN fallback failed for video %d: %s", index, e)
    return None


# ---------------------------------------------------------------------------
# GCS upload helper
# ---------------------------------------------------------------------------

def _upload_to_gcs(local_path: str, org_id: str, creator_username: str) -> str:
    """
    Upload a local video file to GCS and return the gs:// URI.

    Folder structure: phase4-videos/{org_id}/{YYYY-MM-DD}/{creator_username}/{uuid}.mp4

    The bucket lifecycle rule (Age=2 days → Delete) handles eventual cleanup.
    Videos are also deleted immediately after analysis via _delete_gcs_objects().
    """
    from google.cloud import storage

    bucket_name = settings.phase4_gcs_bucket
    today = date.today().isoformat()                     # e.g. 2026-04-16
    blob_name = f"phase4-videos/{org_id}/{today}/{creator_username}/{uuid.uuid4().hex}.mp4"

    client = storage.Client(project=settings.gcp_project)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    size_mb = os.path.getsize(local_path) / (1024 * 1024)
    print(f"[Phase4] Uploading {size_mb:.1f} MB → gs://{bucket_name}/{blob_name}")
    blob.upload_from_filename(local_path, content_type="video/mp4")
    print(f"[Phase4] ✅ Upload complete → gs://{bucket_name}/{blob_name}")

    return f"gs://{bucket_name}/{blob_name}"


def _delete_gcs_objects(gcs_uris: list[str]) -> None:
    """Delete GCS objects immediately after analysis. Lifecycle rule is a safety net."""
    from google.cloud import storage

    client = storage.Client(project=settings.gcp_project)
    for uri in gcs_uris:
        try:
            # gs://bucket/path  →  bucket, path
            without_prefix = uri[len("gs://"):]
            bucket_name, blob_name = without_prefix.split("/", 1)
            client.bucket(bucket_name).blob(blob_name).delete()
            print(f"[Phase4] 🗑️  Deleted GCS object: {uri}")
        except Exception as e:
            logger.warning("[Phase4] Could not delete GCS object %s: %s", uri, e)


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------

def run_phase4_analysis(
    product_id: str,
    product_title: str,
    creator_username: str,
    video_ids: list[str],
    web_urls: list[str] | None = None,
    play_url_fallbacks: list[str] | None = None,
    org_id: str = "default",
) -> dict:
    """
    Download videos → upload to GCS → pass gs:// URIs to Gemini 2.5 for
    rubric-based visual evaluation. GCS avoids the Vertex AI inline size limit.
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
    rubric_str = format_rubric_for_prompt(product_id)
    temp_files: list[str] = []
    gcs_uris: list[str] = []
    video_parts: list[Part] = []

    for i in range(min(3, max(len(ids), len(urls)))):
        vid_id = ids[i] if i < len(ids) else None
        web_url = urls[i] if i < len(urls) else None
        fallback_url = fallbacks[i] if i < len(fallbacks) else None

        path = None

        if web_url:
            path = _download_with_ytdlp(web_url, i + 1)
        if not path and vid_id:
            print(f"[Phase4] yt-dlp failed for video {i+1}, trying TikAPI SDK...")
            path = _download_video_with_tikapi_sdk(vid_id, i + 1)
        if not path and fallback_url:
            print(f"[Phase4] Trying raw CDN as last resort for video {i+1}...")
            path = _download_video_raw_fallback(fallback_url, i + 1)

        if not path:
            logger.warning("[Phase4] All download methods failed for video %d — skipping.", i + 1)
            continue

        temp_files.append(path)

        # Upload to GCS and use URI — no inline size limit
        try:
            gcs_uri = _upload_to_gcs(path, org_id=org_id, creator_username=creator_username)
            gcs_uris.append(gcs_uri)
            video_parts.append(Part.from_uri(gcs_uri, mime_type="video/mp4"))
        except Exception as upload_err:
            logger.error("[Phase4] GCS upload failed for video %d: %s", i + 1, upload_err)

    if not video_parts:
        return {
            "visual_score": None,
            "reasoning": (
                "Phase 4 video download or GCS upload failed. "
                "Check that PHASE4_GCS_BUCKET is set and the service account has "
                "storage.objects.create permission on that bucket."
            ),
            "matched_patterns": [],
            "missing_patterns": [],
            "videos_downloaded": 0,
        }

    print(f"[Phase4] Sending {len(video_parts)} GCS video URI(s) to Vertex AI.")

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

        # Retry strategy for 429 Resource Exhausted errors.
        RETRY_WAITS = [2, 4]  # waits in seconds before each retry attempt
        response = None
        for attempt in range(len(RETRY_WAITS) + 1):
            try:
                response = model.generate_content(
                    contents,
                    generation_config=GenerationConfig(temperature=1.0),
                )
                break  # success — exit retry loop
            except Exception as retry_exc:
                is_quota_error = (
                    "429" in str(retry_exc)
                    or "RESOURCE_EXHAUSTED" in str(retry_exc).upper()
                )
                if is_quota_error and attempt < len(RETRY_WAITS):
                    wait_sec = RETRY_WAITS[attempt]
                    logger.warning(
                        "[Phase4] 429 quota hit on attempt %d/%d — waiting %ds before retry.",
                        attempt + 1, len(RETRY_WAITS) + 1, wait_sec,
                    )
                    time.sleep(wait_sec)
                else:
                    # Not a quota error, or we have exhausted all retries
                    raise

        raw_text = response.text
        logger.info("[Phase4] Gemini video analysis complete.")

        # Parse structured output using LangChain wrapper
        structured_llm = ChatGoogleGenerativeAI(
            model=settings.vertex_model,
            project=settings.gcp_project,
            location="us-central1",
            temperature=0,
            vertexai=True,
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
        import traceback
        logger.error(
            "[Phase4] Gemini video analysis failed: %s\nType: %s\nTraceback:\n%s",
            e, type(e).__name__, traceback.format_exc(),
        )
        if hasattr(e, "details") and callable(e.details):
            logger.error("[Phase4] gRPC error details: %s", e.details())
        return {
            "visual_score": 0,
            "reasoning": f"Phase 4 analysis failed: {str(e)}",
            "matched_patterns": [],
            "missing_patterns": [],
            "videos_downloaded": len(video_parts),
        }

    finally:
        # 1. Delete GCS objects immediately (lifecycle rule is just a safety net)
        if gcs_uris:
            _delete_gcs_objects(gcs_uris)
        # 2. Clean up local temp files
        for path in temp_files:
            try:
                os.unlink(path)
            except Exception:
                pass
