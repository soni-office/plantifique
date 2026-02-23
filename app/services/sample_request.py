import requests
from app.core.config import settings
import time 
from app.utils.api_sign import generate_sign
from urllib.parse import urlencode


def sample_request(access_token: str, shop_cipher: str, page_size: int = 20, page_token: str = None):
    uri=f"{settings.base_url}/affiliate_seller/202508/sample_applications/search"
    timestamp = int(time.time())
    qs = {
        "app_key": settings.app_key,
        "timestamp": timestamp,
        "page_size": page_size,
        "shop_cipher": shop_cipher
    }
    print("query parameters", qs)
    
    if page_token:
        qs["page_token"] = page_token

    headers = {
        "content-type": "application/json",
        "x-tts-access-token": access_token
    }

    body = {}

    request_option = {
        "uri": uri,
        "qs": qs,
        "headers": headers,
        "body": body
    }

    sign = generate_sign(request_option, settings.app_secret)
    qs["sign"] = sign

    final_url = uri + "?" + urlencode(qs)

    response = requests.post(final_url, headers=headers)
    return response.json()

