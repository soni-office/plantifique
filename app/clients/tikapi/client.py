import logging
from typing import Optional

import requests
from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.tikapi.io"


class TikApiClient:
    """Handles all raw HTTP communication with TikAPI."""

    def __init__(self):
        self.base_url = _BASE_URL
        self.api_key = settings.tikapi_key

    def _headers(self) -> dict:
        return {
            "content-type": "application/json",
            "X-API-KEY": self.api_key,
        }

    def _get(self, path: str, params: dict, timeout: int = 10) -> Optional[dict]:
        if not self.api_key:
            logger.warning("[TikAPI] API key missing - skipping user lookup.")
            return None
        
        try:
            url = f"{self.base_url}{path}"
            resp = requests.get(url, headers=self._headers(), params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error("[TikAPI] GET %s failed: %s", path, e)
            return None

    # ----------- PUBLIC METHODS -----------

    def get_user_by_username(self, username: str) -> Optional[dict]:
        data = self._get("/public/check", {"username": username})
        if not data:
            return None
        return data.get("userInfo") or data.get("user")

    def get_user_playlists(self, sec_uid: str) -> list[dict]:
        data = self._get("/public/playlists", {"secUid": sec_uid})
        if not data:
            return []
        return data.get("cursorList") or data.get("mixList") or data.get("mixInfo") or []

    def get_playlist_videos(self, mix_id: str, limit: int = 10) -> list[dict]:
        data = self._get("/public/playlist/items", {"id": mix_id, "count": limit})
        if not data:
            return []
        return data.get("itemList") or []

    def get_top_videos(self, sec_uid: str, limit: int = 10) -> list[dict]:
        data = self._get("/public/posts", {"secUid": sec_uid, "count": limit}, timeout=15)
        if not data:
            return []
        return data.get("itemList") or []

    def get_video_comments(self, video_id: str, limit: int = 5) -> list[dict]:
        data = self._get("/public/comment/list", {"media_id": video_id, "count": limit})
        if not data:
            return []
        return data.get("comments") or []