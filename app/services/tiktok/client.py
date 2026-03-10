import json
import time
import requests
from urllib.parse import urlencode
from app.core.config import settings
from app.utils.api_sign import generate_sign


class TikTokClient:

    @staticmethod
    def post(path: str, access_token: str, shop_cipher: str, qs: dict, body: dict):
        path_only=path
        uri = f"{settings.base_url}{path_only}"
        print(">>>>>>>", shop_cipher)
        headers = {
            "content-type": "application/json",
            "x-tts-access-token": access_token,
        }

        qs.update({
            "app_key": settings.app_key,
            "timestamp": int(time.time()),
            "page_size": qs.get("page_size", 20),
            "shop_cipher": shop_cipher,
        })
        request_option = {
            "uri" : uri,
            "qs": qs,
            "headers": headers,
            "body": body,
        }

        sign = generate_sign(request_option, settings.app_secret)
        qs["sign"] = sign
        
        sorted_qs = dict(sorted(qs.items()))
        final_url = f"{uri}?{urlencode(sorted_qs)}"

        print("Final URL:", final_url)
        print("Request Body:", json.dumps(body, separators=(",", ":")))
        response = requests.post(final_url, headers=headers, json=body)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def get(path: str, access_token: str, shop_cipher: str, qs: dict):
        path_only = path
        uri = f"{settings.base_url}{path_only}"

        headers = {
            "content-type": "application/json",
            "x-tts-access-token": access_token,
        }

        qs.update({
            "app_key": settings.app_key,
            "timestamp": int(time.time()),
            "shop_cipher": shop_cipher,
        })

        request_option = {
            "uri": path_only,
            "qs": qs,
            "headers": headers,
            "body": {},
        }

        sign = generate_sign(request_option, settings.app_secret)
        qs["sign"] = sign

        sorted_qs = dict(sorted(qs.items()))
        final_url = f"{uri}?{urlencode(sorted_qs)}"

        print("Final URL:", final_url)
        # breakpoint()
        response = requests.get(final_url, headers=headers)
        response.raise_for_status()
        return response.json()