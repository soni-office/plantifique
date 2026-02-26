
import secrets
import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.repository.oauth_state_repository import OAuthStateRepository
from app.repository.user_repository import UserRepository
from app.repository.tiktok_token_repository import TikTokTokenRepository
from app.schemas.auth import OAuthExchangeRequest
from app.services.tiktok.oauth_service import TikTokOAuthService
from app.core.security import create_access_token

router = APIRouter(prefix="/auth/tiktokshop", tags=["TikTok Shop OAuth"])

logger = logging.getLogger(__name__)


@router.get("/callback")
async def callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    state_repo = OAuthStateRepository(db)
    db_state = state_repo.get_by_state(state)

    if not db_state:
        raise HTTPException(status_code=400, detail="Invalid state")

    frontend_callback = (
        f"{settings.frontend_url.rstrip('/')}/"
        f"{settings.frontend_oauth_callback_path.lstrip('/')}"
    )
    query = urlencode({"code": code, "state": state})

    return RedirectResponse(url=f"{frontend_callback}?{query}")


@router.get("/login")
async def login(db: Session = Depends(get_db)):
    state = secrets.token_urlsafe(32)

    state_repo = OAuthStateRepository(db)
    state_repo.create(state)
    db.commit()

    auth_url = TikTokOAuthService.get_auth_url(state)

    return RedirectResponse(url=auth_url)


@router.post("/exchange")
async def exchange(payload: OAuthExchangeRequest, db: Session = Depends(get_db)):
    code = payload.code
    state = payload.state

    state_repo = OAuthStateRepository(db)
    db_state = state_repo.get_by_state(state)

    if not db_state:
        raise HTTPException(status_code=400, detail="Invalid state")

    state_repo.delete(db_state)
    db.commit()

    token_data = TikTokOAuthService.exchange_code_for_token(code)

    open_id = token_data.get("open_id") or token_data.get("seller_id")

    user_repo = UserRepository(db)
    user = user_repo.get_by_tiktok_open_id(open_id)

    if not user:
        user = user_repo.create(open_id=open_id)
        db.commit()

    token_repo = TikTokTokenRepository(db)
    token_row = token_repo.get_by_user_id(user.id)

    if not token_row:
        token_row = token_repo.create(user.id)

    token_row.access_token = token_data["access_token"]
    token_row.refresh_token = token_data["refresh_token"]
    token_row.access_token_expire_in = token_data["access_token_expire_in"]

    db.commit()

    app_token = create_access_token(str(user.id))

    return {
        "access_token": app_token,
        "user": {
            "id": str(user.id),
            "username": user.username,
            "tiktokShopId": user.tiktok_open_id,
        },
    }
