from urllib.parse import urlencode
from datetime import datetime, timezone
import requests
from sqlalchemy import text 
from app.core.config import settings


def get_auth_url(state: str) -> str:
    query = urlencode(
        {
            'app_key': settings.app_key,
            'redirect_uri': settings.redirect_uri,
            'state': state,
        }
    )
    return f'{settings.auth_url}?{query}'


def exchange_code_for_token(code: str) -> dict:
    params = {
        'app_key': settings.app_key,
        'app_secret': settings.app_secret,
        'auth_code': code,
        'grant_type': 'authorized_code',
    }

    response = requests.get(settings.token_url, params=params, timeout=20)
    print("insdie exchange code for token", response)
    response.raise_for_status()

    payload = response.json()
    print(" payload -----", payload)
    data = payload.get('data', {})
    if not data.get('access_token'):
        raise ValueError('TikTok token response missing access_token')

    return data


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



def get_valid_access_token(db):
    token_row = db.execute(
        text(
            "SELECT id, access_token, refresh_token, access_token_expire_in FROM tiktok_tokens ORDER BY id DESC LIMIT 1"
        )
        
    ).fetchone()

    if not token_row:
        raise ValueError("No TikTok token found in DB. Please login again.")

    token_id = token_row.id
    access_token = token_row.access_token
    refresh_token = token_row.refresh_token
    expiry = token_row.access_token_expire_in

    now = datetime.now(timezone.utc).timestamp()

    # if token expired -> refresh
    if now >= expiry:
        new_data = refresh_access_token(refresh_token)

        new_access_token = new_data["access_token"]
        new_refresh_token = new_data["refresh_token"]
        new_expiry = new_data["access_token_expire_in"] + int(now)

        db.execute(
            """
            UPDATE tiktok_tokens
            SET access_token = %s,
                refresh_token = %s,
                access_token_expire_in = %s
            WHERE id = %s
            """,
            (new_access_token, new_refresh_token, new_expiry, token_id),
        )
        db.commit()

        return new_access_token

    return access_token



