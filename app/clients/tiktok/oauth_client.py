"""
Raw TikTok OAuth HTTP calls — no business logic, no FastAPI dependencies.
"""
import logging
import requests
from urllib.parse import urlencode

from app.core.config import settings

logger = logging.getLogger(__name__)


class TikTokOAuthClient:

    @staticmethod
    def get_auth_url(state: str) -> str:
        """Build the TikTok authorization URL for the OAuth redirect."""
        query = urlencode({
            "app_key": settings.app_key,
            "redirect_uri": settings.redirect_uri,
            "state": state,
        })
        return f"{settings.auth_url}?{query}"

    @staticmethod
    def exchange_code(code: str) -> dict:
        """
        Exchange an auth code for access + refresh tokens.
        Returns the ``data`` sub-object from TikTok's response.
        Raises ValueError on API-level errors.
        """
        params = {
            "app_key": settings.app_key,
            "app_secret": settings.app_secret,
            "auth_code": code,
            "grant_type": "authorized_code",
        }
        response = requests.get(settings.token_url, params=params)

        payload = response.json()
        logger.info("TikTok token exchange response: %s", payload)

        if not response.ok:
            raise ValueError(
                f"TikTok token API HTTP {response.status_code}: {payload}"
            )

        data = payload.get("data")
        if not data:
            code_val = payload.get("code")
            message = payload.get("message", "Unknown error from TikTok")
            request_id = payload.get("request_id", "")
            raise ValueError(
                f"TikTok auth failed: {message} (code={code_val}, request_id={request_id})"
            )

        return data

    @staticmethod
    def refresh_token(refresh_token: str) -> dict:
        """
        Silently refresh an expired access token.
        Returns the ``data`` sub-object. Raises ValueError if the new access_token is missing.
        """
        params = {
            "app_key": settings.app_key,
            "app_secret": settings.app_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
        response = requests.get(settings.refresh_token_url, params=params, timeout=25)
        response.raise_for_status()

        data = response.json().get("data", {})
        if not data.get("access_token"):
            raise ValueError("TikTok refresh response missing access_token")
        return data
