from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse
import os 
from app.services.tiktokshop_oauth import get_auth_url, exchange_code_for_token
from dotenv import load_dotenv
load_dotenv()
FRONTEND_URL = os.getenv("FRONTEND_URL")
router = APIRouter(prefix="/auth/tiktokshop", tags=["TikTok Shop OAuth"])


@router.get("/login")
def login():
    """
    Redirect seller to TikTok authorization page.
    """
    url = get_auth_url()
    print(url)
    return RedirectResponse(url)

@router.get("/callback")
def callback(code: str = Query(...), state: str = Query(...)):
    token_data = exchange_code_for_token(code)

    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")

    # TODO: store tokens securely in DB (recommended)
    # save_tokens(shop_id, access_token, refresh_token)

    # Redirect user to frontend dashboard
    return RedirectResponse(url=FRONTEND_URL)
