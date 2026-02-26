import requests
from urllib.parse import urlencode
from app.core.config import settings


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
        params = {
            "app_key": settings.app_key,
            "app_secret": settings.app_secret,
            "auth_code": code,
            "grant_type": "authorized_code",
        }
        response = requests.get(settings.token_url, params=params)
        response.raise_for_status()
        return response.json()["data"]

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

