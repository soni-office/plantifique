# app/services/tikapi/service.py

import json
import logging
from typing import Optional

from langchain_google_vertexai import ChatVertexAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.clients.tikapi.client import TikApiClient

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
        self.client = TikApiClient()
        self.llm = ChatVertexAI(
            model_name=settings.vertex_model,
            temperature=0
        ).with_structured_output(PlaylistSelection)

    # ---------- PUBLIC ENTRY POINT ----------

    def enrich_creator(self, username: str, product_title: Optional[str] = None) -> list[dict]:
        user_info = self.client.get_user_by_username(username)
        if not user_info:
            return []

        user = user_info.get("user") or user_info
        sec_uid = user.get("secUid") or user.get("id")

        if not sec_uid:
            return []

        videos = self._get_relevant_videos(sec_uid, username, product_title)

        # Enrich top 5 videos with comments
        for video in videos[:5]:
            video_id = video.get("video_id")
            if video_id:
                comments = self._get_clean_comments(video_id)
                video["top_comments"] = comments

        return videos

    # ---------- INTERNAL LOGIC ----------

    def _get_relevant_videos(self, sec_uid: str, username: str, product_title: Optional[str]):
        # TODO: Later we can experiment with using a mix of top videos and playlist videos to see if it improves the reasoning.
        if product_title:
            playlists = self.client.get_user_playlists(sec_uid)
            mix_id = self._select_playlist(playlists, product_title)

            if mix_id:
                raw = self.client.get_playlist_videos(mix_id, _VIDEO_LIMIT)
                return [self._sanitise_video(v, username) for v in raw]

        # fallback
        raw = self.client.get_top_videos(sec_uid, _VIDEO_LIMIT)
        return [self._sanitise_video(v, username) for v in raw]

    def _select_playlist(self, playlists: list[dict], product_title: str) -> Optional[str]:
        if not playlists:
            return None

        prompt = f"""
Product: {product_title}

Playlists:
{json.dumps([{"mix_name": p.get("mixName"), "mix_id": p.get("mixId")} for p in playlists if p.get("mixId")], indent=2)}

Return the most relevant mix_id or null.
"""

        try:
            result = self.llm.invoke(prompt)
            return result.selected_mix_id
        except Exception as e:
            logger.warning("Playlist selection failed: %s", e)
            return None

    def _get_clean_comments(self, video_id: str) -> list[str]:
        raw = self.client.get_video_comments(video_id, _COMMENT_LIMIT)
        return [
            (c.get("text") or "")[:_COMMENT_MAX_CHARS].strip()
            for c in raw if c.get("text")
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