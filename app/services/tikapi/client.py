"""
TikAPI Service — Creator Video & Profile Enrichment.

"""
import logging
from typing import Optional

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.tikapi.io"
_VIDEO_LIMIT = 10
_COMMENT_LIMIT = 5
_CAPTION_MAX_CHARS = 250
_COMMENT_MAX_CHARS = 150


def _headers() -> dict:
    return {
        "X-API-KEY": settings.tikapi_key,
        "Content-Type": "application/json",
    }


class TikApiService:
    """
    Wraps the TikAPI.io REST endpoints needed for creator enrichment.

    """

    @staticmethod
    def get_user_by_username(username: str) -> Optional[dict]:
        """Resolve a TikTok @username to a TikAPI user profile."""
        if not settings.tikapi_key:
            logger.warning("[TikAPI] TIKAPI_KEY not configured — skipping user lookup.")
            return None

        try:
            url = f"{_BASE_URL}/public/check"
            resp = requests.get(url, headers=_headers(), params={"username": username}, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            user_info = data.get("userInfo") or data.get("user")
            if not user_info:
                logger.warning("[TikAPI] No userInfo for username=%s. Response: %s", username, data)
            return user_info
        except requests.RequestException as e:
            logger.error("[TikAPI] get_user_by_username failed for %s: %s", username, e)
            return None

    @staticmethod
    def get_top_videos(sec_uid: str, username: str, limit: int = _VIDEO_LIMIT) -> list[dict]:
        """
        Fetch the most recent public videos for a creator.
        Returns sanitised video dicts without comments (comments are fetched separately).
        """
        if not settings.tikapi_key:
            logger.warning("[TikAPI] TIKAPI_KEY not configured — skipping video fetch.")
            return []

        try:
            url = f"{_BASE_URL}/public/posts"
            resp = requests.get(
                url,
                headers=_headers(),
                params={"secUid": sec_uid, "count": limit},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_videos = data.get("itemList") or []
            return [TikApiService._sanitise_video(v, username) for v in raw_videos[:limit]]
        except requests.RequestException as e:
            logger.error("[TikAPI] get_top_videos failed for sec_uid=%s: %s", sec_uid, e)
            return []

    @staticmethod
    def get_video_comments(video_id: str, limit: int = _COMMENT_LIMIT) -> list[str]:
        """
        Fetch the top comments for a single video.
        
        """
        if not settings.tikapi_key:
            return []

        try:
            url = f"{_BASE_URL}/public/comment/list"
            resp = requests.get(
                url,
                headers=_headers(),
                params={"media_id": video_id, "count": limit},
                timeout=10,
            )
            resp.raise_for_status()
            data = resp.json()
            raw_comments = data.get("comments") or []
            return [
                (c.get("text") or "")[:_COMMENT_MAX_CHARS].strip()
                for c in raw_comments[:limit]
                if c.get("text")
            ]
        except requests.RequestException as e:
            logger.warning("[TikAPI] get_video_comments failed for video_id=%s: %s", video_id, e)
            return []

    @staticmethod
    def _sanitise_video(item: dict, username: str) -> dict:
        """
        Extract only the fields the AI prompt needs.
        Captions are truncated to keep token usage and cost predictable.
        Comments are NOT fetched here — they are added in enrich_creator().
        """
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
            "top_comments": [],  # populated by enrich_creator()
        }

    @classmethod
    def enrich_creator(cls, username: str) -> list[dict]:
        """
        Helper: given a @username, return their top videos
        each enriched with top audience comments.

        Comment fetching is done only for the first 5 videos to limit
        API calls (5 videos × 1 API call = 5 total comment requests).
        """
        user_info = cls.get_user_by_username(username)
        if not user_info:
            return []

        user = user_info.get("user") or user_info
        sec_uid = user.get("secUid") or user.get("id")
        if not sec_uid:
            logger.warning("[TikAPI] Could not extract secUid for username=%s", username)
            return []

        videos = cls.get_top_videos(sec_uid=sec_uid, username=username)
        logger.info("[TikAPI] Fetched %d videos for username=%s", len(videos), username)

        # Enrich the first 5 videos with top comments (audience vibe signal)
        for i, video in enumerate(videos[:5]):
            video_id = video.get("video_id")
            if video_id:
                comments = cls.get_video_comments(video_id=video_id)
                video["top_comments"] = comments
                logger.debug(
                    "[TikAPI] Fetched %d comments for video_id=%s (video %d/%d)",
                    len(comments), video_id, i + 1, min(5, len(videos))
                )

        return videos
