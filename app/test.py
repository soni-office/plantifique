import time
import hmac
import hashlib
import json
import requests
from urllib.parse import urlparse, urlencode


# def generate_sign(request_option, app_secret):
#     """
#     Generate HMAC-SHA256 signature for TikTok Shop API
#     """

#     # Step 1: Extract query parameters, exclude access_token and sign
#     params = request_option.get("qs", {})
#     exclude_keys = ["access_token", "sign"]

#     sorted_params = [
#         {"key": key, "value": str(params[key])}
#         for key in sorted(params.keys())
#         if key not in exclude_keys
#     ]

#     # Step 2: Concatenate parameters in {key}{value} format
#     param_string = "".join([f"{item['key']}{item['value']}" for item in sorted_params])

#     # Step 3: Append request path
#     uri = request_option.get("uri", "")
#     pathname = urlparse(uri).path
#     sign_string = f"{pathname}{param_string}"

#     # Step 4: Append body if exists and not multipart/form-data
#     content_type = request_option.get("headers", {}).get("content-type", "")
#     body = request_option.get("body", {})

#     if content_type != "multipart/form-data" and body:
#         body_str = json.dumps(body, separators=(",", ":"))
#         sign_string += body_str

#     # Step 5: Wrap with app_secret
#     wrapped_string = f"{app_secret}{sign_string}{app_secret}"

#     # Step 6: HMAC-SHA256
#     sign = hmac.new(
#         app_secret.encode("utf-8"),
#         wrapped_string.encode("utf-8"),
#         hashlib.sha256
#     ).hexdigest()

#     return sign

import hmac  
import hashlib  
from urllib.parse import urlparse  
import json  
  
def generate_sign(request_option, app_secret):  
    """  
    Generate HMAC-SHA256 signature  
    :param request_option: Request options dictionary containing qs (query params), uri (path), headers, body etc.  
    :param app_secret: Secret key for signing  
    :return: Hexadecimal signature string  
    """  
    # Step 1: Extract and filter query parameters, exclude "access_token" and "sign", sort alphabetically  
    params = request_option.get('qs', {})  
    exclude_keys = ["access_token", "sign"]  
    sorted_params = [  
        {"key": key, "value": params[key]}  
        for key in sorted(params.keys())  
        if key not in exclude_keys  
    ]  
  
    # Step 2: Concatenate parameters in {key}{value} format  
    param_string = ''.join([f"{item['key']}{item['value']}" for item in sorted_params])  
    sign_string = param_string  
  
    # Step 3: Append API request path to the signature string  
    uri = request_option.get('uri', '')  
    pathname = urlparse(uri).path if uri else ''  
    sign_string = f"{pathname}{param_string}"  
  
    # Step 4: If not multipart/form-data and request body exists, append JSON-serialized body  
    content_type = request_option.get('headers', {}).get('content-type', '')  
    body = request_option.get('body', {})  
    if content_type != 'multipart/form-data' and body:  
        body_str = json.dumps(body)  # JSON serialization ensures consistency  
        sign_string += body_str  
  
    # Step 5: Wrap signature string with app_secret  
    wrapped_string = f"{app_secret}{sign_string}{app_secret}"  
  
    # Step 6: Encode using HMAC-SHA256 and generate hexadecimal signature  
    hmac_obj = hmac.new(  
        app_secret.encode('utf-8'),  
        wrapped_string.encode('utf-8'),  
        hashlib.sha256  
    )  
    sign = hmac_obj.hexdigest()  
    return sign


# if __name__ == "__main__":

#     APP_KEY = "6j17thd2h3k6e"
#     APP_SECRET = "15fec1a4aa7ddb15692ef2c07ae9bdb70169ed20"
#     ACCESS_TOKEN = "TTP_sA_32wAAAABOYrV3ZxH42vLvRCv_132NDY2s8xz7ub4NeJmcTrl3eb_sdirMGJAiQdveywonEfT2yJwPjGfpGlRP78Vrqhi4n-5Ww-GaVJJvfs-DS3E6KHcu20twZb-DTa3Rz-doHjA"
#     timestamp = int(time.time())

#     # API endpoint
#     product_id=1732268131939881168
#     uri ="https://open-api.tiktokglobalshop.com/affiliate_seller/202406/marketplace_creators/search"
   
#     page_size=12
#     cipher="TTP_QaxVSgAAAACI9jDpQr8EtjBL2HxeuNuw"
#     # Query params
#     qs = {
#         "app_key": APP_KEY,
#         "timestamp": timestamp,
#         "page_size": page_size,
#         "shop_cipher": cipher
#     }

#     # Headers
#     headers = {
#         "content-type": "application/json",
#         "x-tts-access-token": ACCESS_TOKEN,
       
#     }

#     # Body (GET request has no body)
#     body = {
       
#     }

#     # Build request options
#     request_option = {
#         "uri": uri,
#         "qs": qs,
#         "headers": headers,
#         "body": body
#     }

#     # Generate sign
#     sign = generate_sign(request_option, APP_SECRET)

#     # Build final URL
#     qs["sign"] = sign
#     final_url = uri + "?" + urlencode(qs)

#     print("Final URL:", final_url)
#     print("Timestamp:", timestamp)
#     print("Sign:", sign)

#     # Call API
#     response = requests.post(final_url, headers=headers)

#     print("\nStatus Code:", response.status_code)
#     print("Response:", response.text)
    
    
#     # "cipher":"TTP_QaxVSgAAAACI9jDpQr8EtjBL2HxeuNuw"



if __name__ == "__main__":

    APP_KEY = "6j17thd2h3k6e"
    APP_SECRET = "15fec1a4aa7ddb15692ef2c07ae9bdb70169ed20"
    ACCESS_TOKEN = "TTP_FPjhKgAAAABOYrV3ZxH42vLvRCv_132NDY2s8xz7ub4NeJmcTrl3eZ9368BVt8tU8u4VBsGbE2IGp0MBz5nZ3-2ZNIB_Ft1gomAmxuFGrSrad2SfuyJX8Bd0M3730BV5QGdzJMVkoVw"
    BASE_URL = "https://open-api.tiktokglobalshop.com"

    timestamp = int(time.time())

    path = "/affiliate_seller/202406/marketplace_creators/search"
    url = BASE_URL + path

    cipher = "TTP_QaxVSgAAAACI9jDpQr8EtjBL2HxeuNuw"

    qs = {
        "app_key": APP_KEY,
        "timestamp": timestamp,
        "page_size": 12,
        "shop_cipher": cipher
    }

    headers = {
        "content-type": "application/json",
        "x-tts-access-token": ACCESS_TOKEN,
    }

    body = {
        "keyword": "JefreeStar",
        "gmv_ranges": ["GMV_RANGE_0_100"],
        "units_sold_ranges": ["UNITS_SOLD_RANGE_0_10"]
    }

    request_option = {
        "uri": path,      # IMPORTANT: path only
        "qs": qs,
        "headers": headers,
        "body": body
    }

    sign = generate_sign(request_option, APP_SECRET)

    qs["sign"] = sign

    final_url = url + "?" + urlencode(dict(sorted(qs.items())))

    print("Final URL:", final_url)
    print("Body used for sign:", json.dumps(body, separators=(",", ":")))

    response = requests.post(
        final_url,
        headers=headers,
        json=body
    )

    print("Status Code:", response.status_code)
    print("Response:", response.text)