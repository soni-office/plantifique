import requests
from app.core.config import settings
import time 
from app.services.tiktokshop_oauth import get_valid_access_token
from app.utils.api_sign import generate_sign
from urllib.parse import urlencode
from app.db.database import get_db
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session



def shop_cipher(db: Session):
    url=f"{settings.base_url}/authorization/202309/shops"
    access_token=get_valid_access_token(db)
    headers={
        "content-type": "application/json",
        "x-tts-access-token": access_token
    }
    print("access token -----",access_token)
    qs={
            "app_key": settings.app_key,
            "timestamp": int(time.time())
        }
    body={}
    request_option={
        "uri": url,
        "qs":qs,
        "headers": headers,
        "body": body
    }
    
    sign=generate_sign(request_option, settings.app_secret)
    qs["sign"] = sign
    
    
    final_url = url + "?" + urlencode(qs)
    print("shop cipher url : ",final_url)

    response = requests.get(final_url, headers=headers)
    return response.json()