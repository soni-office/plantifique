import secrets
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.repository.oauth_state_repository import OAuthStateRepository
from app.repository.user_repository import UserRepository
from app.repository.access_token_repository import AccessTokenRepository
from app.schemas.auth import OAuthExchangeRequest
from app.services.tiktok.oauth_service import TikTokOAuthService
from app.core.security import create_jwt_token

router = APIRouter(prefix="/auth/tiktokshop", tags=["TikTok Shop OAuth"])

logger = logging.getLogger(__name__)


@router.get("/login")
async def login():
    """
    Step 1: Redirect the admin to TikTok's OAuth consent screen.
    """
    state = secrets.token_urlsafe(32)

    state_repo = OAuthStateRepository()
    state_repo.create(state)

    auth_url = TikTokOAuthService.get_auth_url(state)
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
):
    """
    Step 2: TikTok redirects here after the admin approves access.
    """
    state_repo = OAuthStateRepository()
    db_state = state_repo.get_by_state(state)

    if not db_state:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    frontend_callback = (
        f"{settings.frontend_url.rstrip('/')}/"
        f"{settings.frontend_oauth_callback_path.lstrip('/')}"
    )
    params: dict = {"code": code}
    if state:
        params["state"] = state
    return RedirectResponse(url=f"{frontend_callback}?{urlencode(params)}")


@router.post("/exchange")
async def exchange(payload: OAuthExchangeRequest):
    """
    Step 3: Frontend calls this to exchange the OAuth code for tokens.
    """
    code = payload.code
    state = payload.state

    # --- CSRF validation ---
    state_repo = OAuthStateRepository()
    db_state = None
    if state:
        db_state = state_repo.get_by_state(state)

    if not db_state:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    # State is single-use — delete immediately after validation
    state_repo.delete(db_state["state"])

    # --- Exchange code for TikTok tokens ---
    token_data = TikTokOAuthService.exchange_code_for_token(code)
    open_id = token_data.get("open_id") or token_data.get("seller_id")

    # --- Resolve or create the user (always ORG_ADMIN for this flow) ---
    user_repo = UserRepository()
    user = user_repo.get_by_tiktok_open_id(open_id)

    if not user:
        # First time this TikTok shop connects — create the admin user
        user = user_repo.create(
            org_id=settings.org_id,
            open_id=open_id,
            role="ORG_ADMIN",
        )
        logger.info(
            "New ORG_ADMIN created: user_id=%s org_id=%s tiktok_open_id=%s",
            user["id"],
            settings.org_id,
            open_id,
        )
    else:
        # Update last login timestamp
        user_repo.touch_login(user["id"])
        logger.info(
            "Existing ORG_ADMIN login: user_id=%s org_id=%s",
            user["id"],
            user["org_id"],
        )

    # --- Derive token expiry timestamps ---
    from datetime import datetime, timezone
    now = int(datetime.now(timezone.utc).timestamp())
    access_expires_at = now + int(token_data.get("access_token_expire_in", 3600))
    refresh_expires_at = (
        now + int(token_data["refresh_token_expire_in"])
        if token_data.get("refresh_token_expire_in")
        else None
    )

    # --- Save token at ORG level — all team members will share this ---
    token_repo = AccessTokenRepository()
    token_repo.upsert(
        org_id=settings.org_id,
        issued_by=user["id"],
        tiktok_open_id=open_id,
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        access_token_expires_at=access_expires_at,
        refresh_token_expires_at=refresh_expires_at,
    )

    logger.info(
        "TikTok org-level token saved: org_id=%s issued_by=%s",
        settings.org_id,
        user["id"],
    )

    # --- Issue the app JWT with full org context ---
    app_token = create_jwt_token(
        user_id=user["id"],
        org_id=settings.org_id,
        role=user.get("role", "ORG_ADMIN"),
        tiktok_open_id=open_id,
    )

    return {
        "jwt_token": app_token,
        "access_token": app_token,  # Legacy alias for frontend compatibility
        "token_type": "Bearer",
        "user": {
            "id": user["id"],
            "name": user.get("name"),
            "role": user.get("role", "ORG_ADMIN"),
            "org_id": settings.org_id,
            "tiktokShopId": open_id,
        },
    }
