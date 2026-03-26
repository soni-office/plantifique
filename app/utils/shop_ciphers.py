import requests
import time
from urllib.parse import urlencode
from app.core.config import settings
from app.services.tiktok.token_service import TokenService
from app.utils.api_sign import generate_sign


def shop_cipher(org_id: str):
    url = f"{settings.base_url}/authorization/202309/shops"
    token_service = TokenService()
    access_token = token_service.get_valid_access_token(org_id)
    headers = {
        "content-type": "application/json",
        "x-tts-access-token": access_token
    }
    qs = {
        "app_key": settings.app_key,
        "timestamp": int(time.time())
    }
    body = {}
    request_option = {
        "uri": url,
        "qs": qs,
        "headers": headers,
        "body": body
    }

    sign = generate_sign(request_option, settings.app_secret)
    qs["sign"] = sign

    final_url = url + "?" + urlencode(qs)
    response = requests.get(final_url, headers=headers)
    return response.json()