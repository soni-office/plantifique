import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.api.auth_session import get_current_user, require_role
from app.services.oauth_service import OAuthService
from app.repository.access_token_repository import AccessTokenRepository

router = APIRouter(prefix="/auth/tiktokshop", tags=["TikTok Shop OAuth"])
logger = logging.getLogger(__name__)


@router.get("/status")
async def tiktok_status(caller: dict = Depends(get_current_user)):
    """Return whether this org has an active TikTok Shop token."""
    return OAuthService().get_status(caller["org_id"])


@router.delete("/revoke", status_code=200)
async def revoke_tiktok_access(
    caller: dict = Depends(require_role("ORG_ADMIN", "SUPER_ADMIN")),
):
    """Revoke this org's TikTok Shop token."""
    org_id = caller["org_id"]
    token = AccessTokenRepository().get_by_org(org_id)
    if not token:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No TikTok token found for this org")
    OAuthService().revoke(org_id)
    return {"revoked": True, "org_id": org_id}


@router.get("/connect")
async def connect(
    caller: dict = Depends(require_role("ORG_ADMIN", "SUPER_ADMIN")),
):
    """Step 1: Generate a TikTok OAuth URL for the caller's org."""
    auth_url = OAuthService().get_connect_url(
        org_id=caller["org_id"],
        issued_by=caller["uid"],
    )
    return {"auth_url": auth_url}


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
):
    """Step 2: Exchange TikTok auth code for tokens and redirect to frontend."""
    try:
        redirect_url = OAuthService().handle_callback(code=code, state=state)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    return RedirectResponse(url=redirect_url)
