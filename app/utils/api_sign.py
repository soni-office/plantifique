import time
import hmac
import hashlib
import json
import requests
from urllib.parse import urlparse, urlencode


def generate_sign(request_option, app_secret):
    """
    Generate HMAC-SHA256 signature for TikTok Shop API
    """

    # Step 1: Extract query parameters, exclude access_token and sign
    params = request_option.get("qs", {})
    exclude_keys = ["access_token", "sign"]
    
    sorted_params = [
        {"key": key, "value": str(params[key])}
        for key in sorted(params.keys())
        if key not in exclude_keys
    ]

    # Step 2: Concatenate parameters in {key}{value} format
    param_string = "".join([f"{item['key']}{item['value']}" for item in sorted_params])

    # Step 3: Append request path
    uri = request_option.get("uri", "")
    pathname = urlparse(uri).path
    sign_string = f"{pathname}{param_string}"

    # Step 4: Append body if exists and not multipart/form-data
    content_type = request_option.get("headers", {}).get("content-type", "")
    body = request_option.get("body", {})

    if content_type != "multipart/form-data" and body:
        body_str = json.dumps(body, separators=(",", ":"))
        sign_string += body_str

    # Step 5: Wrap with app_secret
    wrapped_string = f"{app_secret}{sign_string}{app_secret}"

    # Step 6: HMAC-SHA256
    sign = hmac.new(
        app_secret.encode("utf-8"),
        wrapped_string.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()

    return sign