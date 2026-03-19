import logging
import requests
from urllib.parse import urlencode
from fastapi import HTTPException
from app.core.config import settings

logger = logging.getLogger(__name__)


class TikTokOAuthService:

    @staticmethod
    def get_auth_url(state: str) -> str:
        query = urlencode({
            "app_key": settings.app_key,
            "redirect_uri": settings.redirect_uri,
            "state": state,
        })
        return f"{settings.auth_url}?{query}"

    @staticmethod
    def exchange_code_for_token(code: str):
        if settings.mock_tiktok:
            logger.info("[Mock] Simulating TikTok token exchange for code=%s", code)
            return {
                "access_token": "mock_access_token_abc_123",
                "refresh_token": "mock_refresh_token_xyz_789",
                "access_token_expire_in": 3600,
                "refresh_token_expire_in": 7200,
                "open_id": "mock_tiktok_shop_id",
                "seller_name": "Plantifique Mock Shop",
            }

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
            logger.error("TikTok token API HTTP error %s: %s", response.status_code, payload)
            raise HTTPException(
                status_code=502,
                detail=f"TikTok token API error (HTTP {response.status_code}): {payload}",
            )

        data = payload.get("data")
        if not data:
            # TikTok returns errors as: {"code": 1, "message": "...", "request_id": "..."}
            code_val = payload.get("code")
            message = payload.get("message", "Unknown error from TikTok")
            request_id = payload.get("request_id", "")
            logger.error(
                "TikTok token exchange failed — code=%s message=%s request_id=%s",
                code_val, message, request_id,
            )
            raise HTTPException(
                status_code=400,
                detail=f"TikTok auth failed: {message} (code={code_val}, request_id={request_id})",
            )

        return data

    @staticmethod
    def refresh_access_token(refresh_token: str) -> dict:
        params = {
            "app_key": settings.app_key,
            "app_secret": settings.app_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }

        response = requests.get(settings.token_url, params=params, timeout=20)
        response.raise_for_status()

        payload = response.json()
        data = payload.get("data", {})

        if not data.get("access_token"):
            raise ValueError("TikTok refresh response missing access_token")

        return data

