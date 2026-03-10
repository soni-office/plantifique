import secrets
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.repository.oauth_state_repository import OAuthStateRepository
from app.repository.user_repository import UserRepository
from app.repository.tiktok_token_repository import TikTokTokenRepository
from app.schemas.auth import OAuthExchangeRequest
from app.services.tiktok.oauth_service import TikTokOAuthService
from app.core.security import create_jwt_token

router = APIRouter(prefix="/auth/tiktokshop", tags=["TikTok Shop OAuth"])

logger = logging.getLogger(__name__)


def _complete_oauth(code: str, state: str | None) -> dict:
    state_repo = OAuthStateRepository()

    if state:
        # Validate state (CSRF protection) — only happens once here
        db_state = state_repo.get_by_state(state)
        if not db_state:
            raise HTTPException(status_code=400, detail="Invalid state")
        state_repo.delete(state)
    else:
        logger.warning(
            "OAuth exchange called without state parameter. "
            "Skipping CSRF validation (acceptable in sandbox)."
        )

    token_data = TikTokOAuthService.exchange_code_for_token(code)

    open_id = token_data.get("open_id") or token_data.get("seller_id")

    user_repo = UserRepository()
    user = user_repo.get_by_tiktok_open_id(open_id)

    if not user:
        user = user_repo.create(open_id=open_id)

    token_repo = TikTokTokenRepository()
    token_row = token_repo.get_by_user_id(user["id"])

    if not token_row:
        token_row = token_repo.create(user["id"])

    # Update token fields in Firestore
    token_repo.update(token_row["id"], {
        "access_token": token_data["access_token"],
        "refresh_token": token_data["refresh_token"],
        "access_token_expire_in": token_data["access_token_expire_in"],
    })

    app_token = create_jwt_token(user["id"], open_id)

    return {
        "jwt_token": app_token,
        # Keep legacy field for compatibility with older frontend code.
        "access_token": app_token,
        "token_type": "Bearer",
        "user": {
            "id": user["id"],
            "username": user.get("username"),
            "tiktokShopId": user.get("tiktok_open_id"),
        },
    }


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(None),
):
    """
    Pass TikTok callback params back to frontend.
    Frontend will call /exchange to complete token creation/session bootstrap.
    """
    frontend_callback = (
        f"{settings.frontend_url.rstrip('/')}/"
        f"{settings.frontend_oauth_callback_path.lstrip('/')}"
    )
    params: dict = {"code": code}
    if state:
        params["state"] = state
    return RedirectResponse(url=f"{frontend_callback}?{urlencode(params)}")


@router.get("/login")
async def login():
    state = secrets.token_urlsafe(32)

    state_repo = OAuthStateRepository()
    state_repo.create(state)

    auth_url = TikTokOAuthService.get_auth_url(state)

    return RedirectResponse(url=auth_url)


@router.post("/exchange")
async def exchange(payload: OAuthExchangeRequest):
    return _complete_oauth(code=payload.code, state=payload.state)
