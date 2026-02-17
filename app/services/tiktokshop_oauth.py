import os
import requests
import secrets
from dotenv import load_dotenv
load_dotenv()
APP_KEY = os.getenv("APP_KEY")
APP_SECRET = os.getenv("APP_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI")

AUTH_URL = os.getenv("AUTH_URL")
TOKEN_URL = os.getenv("TOKEN_URL")
ACCESS_TOKEN=None
REFRESH_TOKEN=None

def get_auth_url():
    """
    Creates TikTok authorization URL where seller logs in.
    """
    state = secrets.token_urlsafe(16)
    print("app key", APP_KEY)

    url = (
        f"{AUTH_URL}"
        f"?app_key={APP_KEY}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&state={state}"
    )

    return url


def exchange_code_for_token(code: str):
    """
    Exchanges auth_code from TikTok into access_token and refresh_token.
    """
    params = {
        "app_key": APP_KEY,
        "app_secret": APP_SECRET,
        "auth_code": code,
        "grant_type": "authorized_code"
    }

    response = requests.get(TOKEN_URL, params=params)
    ACCESS_TOKEN=response.json().get("data", {}).get("access_token")
    REFRESH_TOKEN=response.json().get("data", {}).get("refresh_token")
    return response.json()
