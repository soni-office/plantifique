import logging
import time
from typing import Optional

import requests
from requests.exceptions import ReadTimeout
from app.core.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.tikapi.io"

# Per-endpoint read timeouts (seconds)
_TIMEOUT_DEFAULT  = 18   # user lookups, comments
_TIMEOUT_PLAYLIST = 18   # playlist metadata + items
_TIMEOUT_VIDEO    = 22   # video post listings (heaviest responses)


class TikApiClient:
    """Handles all raw HTTP communication with TikAPI."""

    def __init__(self):
        self.base_url = _BASE_URL
        self.api_key = settings.tikapi_key
        
        # Singleton connection pool to avoid opening a new TCP connection on every single request
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({
                "content-type": "application/json",
                "X-API-KEY": self.api_key,
            })

    def _get(self, path: str, params: dict, timeout: int = _TIMEOUT_DEFAULT) -> Optional[dict]:
        """
        Make a GET request to TikAPI.

        On ReadTimeout only: retries once with timeout + 5 s.
        All other errors are logged and returned as None immediately (no retry).
        """
        if not self.api_key:
            logger.warning("[TikAPI] API key missing - skipping request.")
            return None

        url = f"{self.base_url}{path}"

        for attempt in (1, 2):
            current_timeout = timeout if attempt == 1 else timeout + 5
            try:
                resp = self.session.get(
                    url,
                    params=params,
                    timeout=current_timeout,
                )

                # 502 Bad Gateway: transient TikAPI server hiccup — retry once after 2s
                if resp.status_code == 502:
                    if attempt == 1:
                        logger.warning(
                            "[TikAPI] GET %s returned 502 Bad Gateway — retrying once in 3s",
                            path,
                        )
                        time.sleep(2)
                        continue
                    logger.error("[TikAPI] GET %s returned 502 again on retry — giving up", path)
                    return None

                resp.raise_for_status()
                return resp.json()

            except ReadTimeout:
                if attempt == 1:
                    logger.warning(
                        "[TikAPI] GET %s read timed out after %ds — retrying once with %ds",
                        path, current_timeout, current_timeout + 5,
                    )
                    continue
                # Second attempt also timed out
                logger.error(
                    "[TikAPI] GET %s timed out on retry (%ds) — giving up",
                    path, current_timeout,
                )
                return None

            except requests.RequestException as e:
                # Non-timeout errors: log and bail immediately, no retry
                logger.error("[TikAPI] GET %s failed: %s", path, e)
                return None

        return None  # unreachable, satisfies type checker

    # ----------- PUBLIC METHODS -----------

    def get_user_by_username(self, username: str) -> Optional[dict]:
        data = self._get("/public/check", {"username": username}, timeout=_TIMEOUT_DEFAULT)
        if not data:
            return None
        return data.get("userInfo") or data.get("user")

    def get_user_playlists(self, sec_uid: str) -> list[dict]:
        data = self._get("/public/playlists", {"secUid": sec_uid}, timeout=_TIMEOUT_PLAYLIST)
        if not data:
            return []
        return data.get("cursorList") or data.get("mixList") or data.get("mixInfo") or []

    def get_playlist_videos(self, mix_id: str, limit: int = 10) -> list[dict]:
        data = self._get("/public/playlist/items", {"id": mix_id, "count": limit}, timeout=_TIMEOUT_PLAYLIST)
        if not data:
            return []
        return data.get("itemList") or []

    def get_top_videos(self, sec_uid: str, limit: int = 10) -> list[dict]:
        data = self._get("/public/posts", {"secUid": sec_uid, "count": limit}, timeout=_TIMEOUT_VIDEO)
        if not data:
            return []
        return data.get("itemList") or []

    def get_video_comments(self, video_id: str, limit: int = 5) -> list[dict]:
        data = self._get("/public/comment/list", {"media_id": video_id, "count": limit}, timeout=_TIMEOUT_DEFAULT)
        if not data:
            return []
        return data.get("comments") or []


# Module-level singleton — requests.Session (connection pool) created once per worker
tikapi_client = TikApiClient()