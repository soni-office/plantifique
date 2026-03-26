import secrets
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.repository.oauth_state_repository import OAuthStateRepository
from app.repository.access_token_repository import AccessTokenRepository
from app.services.tiktok.oauth_service import TikTokOAuthService
from app.api.auth_session import get_current_user, require_role

router = APIRouter(prefix="/auth/tiktokshop", tags=["TikTok Shop OAuth"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def tiktok_status(
    caller: dict = Depends(get_current_user),
):
    """
    Return whether this org has an active TikTok Shop token.

    Used by the frontend to gate dashboard data pages.
    """
    token = AccessTokenRepository().get_by_org(caller["org_id"])
    connected = token is not None and token.get("status") == "ACTIVE"
    return {"connected": connected}


@router.delete("/revoke", status_code=200)
async def revoke_tiktok_access(
    caller: dict = Depends(require_role("ORG_ADMIN", "SUPER_ADMIN")),
):
    """
    Revoke this org's TikTok Shop token.

    Marks the token as REVOKED in Firestore — the shop connection must be
    re-established via /connect to restore access.
    """
    org_id = caller["org_id"]
    token = AccessTokenRepository().get_by_org(org_id)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No TikTok token found for this org",
        )
    AccessTokenRepository().revoke(org_id)
    logger.info("TikTok token revoked org_id=%s by=%s", org_id, caller["uid"])
    return {"revoked": True, "org_id": org_id}


@router.get("/connect")
async def connect(
    caller: dict = Depends(require_role("ORG_ADMIN", "SUPER_ADMIN")),
):
    """
    Step 1 (authenticated): Generate a TikTok OAuth URL for the caller's org.

    Returns JSON with ``auth_url``.  The frontend should redirect the browser
    to that URL (e.g. ``window.location.href = data.auth_url``).

    Only ORG_ADMIN and SUPER_ADMIN may initiate the TikTok shop connection.
    """
    state = secrets.token_urlsafe(32)
    OAuthStateRepository().create(
        state=state,
        org_id=caller["org_id"],
        issued_by=caller["uid"],
    )
    auth_url = TikTokOAuthService.get_auth_url(state)
    logger.info(
        "TikTok connect initiated org_id=%s issued_by=%s",
        caller["org_id"], caller["uid"],
    )
    return {"auth_url": auth_url}


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
):
    """
    Step 2: TikTok redirects here after the shop owner approves access.

    The backend exchanges the code for tokens entirely server-side, stores
    the org-level token in Firestore, then redirects to the frontend.
    No JWT is issued — the user is already authenticated via GCIP.
    """
    state_repo = OAuthStateRepository()
    state_doc = state_repo.get_by_state(state)

    if not state_doc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OAuth state")

    # Single-use — consume immediately
    state_repo.delete(state)

    org_id = state_doc["org_id"]
    issued_by = state_doc["issued_by"]

    # Exchange the auth code for TikTok tokens (mocked when MOCK_TIKTOK=true)
    token_data = TikTokOAuthService.exchange_code_for_token(code)
    open_id = token_data.get("open_id") or token_data.get("seller_id", "")

    now = int(datetime.now(timezone.utc).timestamp())
    access_expires_at = now + int(token_data.get("access_token_expire_in", 3600))
    refresh_expires_at = (
        now + int(token_data["refresh_token_expire_in"])
        if token_data.get("refresh_token_expire_in")
        else None
    )

    # Persist at org level — all team members share this token
    AccessTokenRepository().upsert(
        org_id=org_id,
        issued_by=issued_by,
        tiktok_open_id=open_id,
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        access_token_expires_at=access_expires_at,
        refresh_token_expires_at=refresh_expires_at,
    )

    logger.info(
        "TikTok org-level token saved org_id=%s issued_by=%s open_id=%s",
        org_id, issued_by, open_id,
    )

    # Redirect to frontend dashboard with a success signal
    return RedirectResponse(
        url=f"{settings.frontend_url.rstrip('/')}/auth/tiktokshop/callback?tiktok_connected=true"
    )
