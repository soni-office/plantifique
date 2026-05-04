# app/services/tikapi/service.py

import json
import logging
import time
from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.clients.tikapi.client import tikapi_client
from app.cache import cache, keys, ttl

logger = logging.getLogger(__name__)

_VIDEO_LIMIT = 10
_COMMENT_LIMIT = 5
_CAPTION_MAX_CHARS = 250
_COMMENT_MAX_CHARS = 150


class PlaylistSelection(BaseModel):
    selected_mix_id: str | None = Field(default=None)


class TikApiService:
    """Handles business logic, enrichment, and orchestration."""

    def __init__(self):
        self.client = tikapi_client
        self.llm = ChatGoogleGenerativeAI(
            model=settings.vertex_model,
            temperature=0,
            vertexai=True
        ).with_structured_output(PlaylistSelection)

    # ---------- PUBLIC ENTRY POINT ----------

    def enrich_creator(self, username: str, product_title: Optional[str] = None) -> list[dict]:
        user_info = cache.cache_or_fetch(
            keys.tikapi_creator_profile(username),
            ttl.TIKAPI_CREATOR_PROFILE,
            lambda: self.client.get_user_by_username(username),
        )
        if not user_info:
            return []

        user = user_info.get("user") or user_info
        sec_uid = user.get("secUid") or user.get("id")

        if not sec_uid:
            return []

        logger.info("[TikAPI] 1s gap — after profile lookup, before video fetch")
        time.sleep(1)
        videos = self._get_relevant_videos(sec_uid, username, product_title)

        # Enrich top 5 videos with comments — 1s gap between each call
        for video in videos[:5]:
            video_id = video.get("video_id")
            if video_id:
                logger.info("[TikAPI] 1s gap — before fetching comments for video_id=%s", video_id)
                time.sleep(1)
                comments = self._get_clean_comments(video_id)
                video["top_comments"] = comments

        return videos

    # ---------- INTERNAL LOGIC ----------

    def _get_relevant_videos(self, sec_uid: str, username: str, product_title: Optional[str]):
        # TODO: Later we can experiment with using a mix of top videos and playlist videos to see if it improves the reasoning.
        if product_title:
            playlists = cache.cache_or_fetch(
                keys.tikapi_creator_playlists(sec_uid),
                ttl.TIKAPI_CREATOR_PLAYLISTS,
                lambda: self.client.get_user_playlists(sec_uid),
            )
            mix_id = self._select_playlist(playlists, product_title)

            if mix_id:
                logger.info("[TikAPI] 1s gap — after playlist selection, before fetching playlist videos")
                time.sleep(1)
                # Playlist videos not cached — content changes frequently
                raw = self.client.get_playlist_videos(mix_id, _VIDEO_LIMIT)
                return [self._sanitise_video(v, username) for v in raw]

        # fallback
        raw = cache.cache_or_fetch(
            keys.tikapi_creator_top_videos(sec_uid),
            ttl.TIKAPI_CREATOR_TOP_VIDEOS,
            lambda: self.client.get_top_videos(sec_uid, _VIDEO_LIMIT),
        )
        return [self._sanitise_video(v, username) for v in (raw or [])]

    def _select_playlist(self, playlists: list[dict], product_title: str) -> Optional[str]:
        if not playlists:
            return None

        prompt = f"""You are determining which of a TikTok creator's playlists is most relevant to the product we want them to review.
Product: {product_title}

Creator's Playlists:
{json.dumps([{"mix_name": p.get("mixName"), "mix_id": p.get("mixId")} for p in playlists if p.get("mixId")], indent=2)}

Select the mix_id of the playlist that conceptually matches this product category (even if in another language like Spanish). If none are a good fit (e.g. they are all about gaming or food), return None.
"""
       

        try:
            result = self.llm.invoke(prompt)
            if result and result.selected_mix_id:
                mix_id = result.selected_mix_id
                selected_name = next((p.get("mixName") or p.get("name") for p in playlists if p.get("mixId") == mix_id or p.get("id") == mix_id), "Unknown")
                logger.info(f"[TikAPI] AI selected playlist '{selected_name}' for product '{product_title}'. Fetching tailored videos...")
                return mix_id
            return None
        except Exception as e:
            logger.warning("Playlist selection failed: %s", e)
            return None

    def _get_clean_comments(self, video_id: str) -> list[str]:
        raw = cache.cache_or_fetch(
            keys.tikapi_videos_comments(video_id),
            ttl.TIKAPI_VIDEOS_COMMENTS,
            lambda: self.client.get_video_comments(video_id, _COMMENT_LIMIT),
        )
        return [
            (c.get("text") or "")[:_COMMENT_MAX_CHARS].strip()
            for c in (raw or []) if c.get("text")
        ]

    def _sanitise_video(self, item: dict, username: str) -> dict:
        desc = item.get("desc", "") or ""
        stats = item.get("stats", {})
        video = item.get("video", {})
        video_id = item.get("id")

        return {
            "video_id": video_id,
            "web_url": f"https://www.tiktok.com/@{username}/video/{video_id}" if video_id else None,
            "caption": desc[:_CAPTION_MAX_CHARS].strip(),
            "play_url": video.get("playAddr") or video.get("downloadAddr"),
            "cover_url": video.get("cover"),
            "likes": stats.get("diggCount", 0),
            "comments_count": stats.get("commentCount", 0),
            "shares": stats.get("shareCount", 0),
            "plays": stats.get("playCount", 0),
            "language": item.get("textLanguage") or item.get("lang"),
            "quality": video.get("definition") or video.get("videoQuality"),
            "is_hd": item.get("IsHDBitrate", False),
            "top_comments": [],
        }
    
tikapi_service = TikApiService()