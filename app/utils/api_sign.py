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
