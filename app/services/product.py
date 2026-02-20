import time
import requests
from app.core.config import settings
from urllib.parse import urlencode
from app.utils.api_sign import generate_sign


def product_search(access_token: str, shop_cipher: str, page_size: int = 20, page_token: str = None):
    BASE_URL=settings.base_url
    uri = f"{BASE_URL}/product/202309/products/search"
    timestamp = int(time.time())
    
    qs = {
        "app_key": settings.app_key,
        "timestamp": timestamp,
        "page_size": page_size,
        "shop_cipher": shop_cipher
    }
     
    print("query_parameter",qs)

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
