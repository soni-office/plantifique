from datetime import datetime
from urllib.parse import urlencode
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import get_db
from app.db.models import OAuthState, TikTokToken, User
from app.schemas.auth import OAuthExchangeRequest, OAuthExchangeResponse, UserResponse
from app.services.tiktokshop_oauth import exchange_code_for_token, get_auth_url
from app.utils.security import create_access_token

router = APIRouter(prefix='/auth/tiktokshop', tags=['TikTok Shop OAuth'])


@router.get('/login')
def login(db: Session = Depends(get_db)):
    state = secrets.token_urlsafe(32)
    db.add(OAuthState(state=state))
    db.commit()
    return RedirectResponse(url=get_auth_url(state), status_code=status.HTTP_302_FOUND)


@router.get('/callback')
def callback(code: str = Query(...), state: str = Query(...), db: Session = Depends(get_db)):
    db_state = db.query(OAuthState).filter(OAuthState.state == state).first()
    if not db_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid oauth state')

    callback_url = (
        f"{settings.frontend_url}{settings.frontend_oauth_callback_path}?"
        + urlencode({'code': code, 'state': state})
    )
    return RedirectResponse(url=callback_url, status_code=status.HTTP_302_FOUND)


@router.post('/exchange', response_model=OAuthExchangeResponse)
def exchange(payload: OAuthExchangeRequest, db: Session = Depends(get_db)):
    db_state = db.query(OAuthState).filter(OAuthState.state == payload.state).first()
    if not db_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid oauth state')

    db.delete(db_state)
    db.commit()
    print("inside exchange")
    print("payload -----",payload)
    print("payload code -----",payload.code)
    token_data = exchange_code_for_token(payload.code)
    print("token ------",token_data)
    open_id = token_data.get('open_id') or token_data.get('seller_id')
    if not open_id:
        open_id = f"tiktok_{secrets.token_hex(8)}"

    user = db.query(User).filter(User.tiktok_open_id == open_id).first()
    if not user:
        user = User(
            tiktok_open_id=open_id,
            username=token_data.get('seller_name'),
        )
        print("NNNNNNN",user)
        db.add(user)
        
        db.flush()

    token_row = db.query(TikTokToken).filter(TikTokToken.user_id == user.id).first()
    if not token_row:
        token_row = TikTokToken(user_id=user.id, access_token=token_data['access_token'])
        db.add(token_row)

    token_row.access_token = token_data.get('access_token')
    token_row.refresh_token = token_data.get('refresh_token')
    token_row.scope = token_data.get('scope')
    token_row.access_token_expire_in = token_data.get('access_token_expire_in')
    token_row.refresh_token_expire_in = token_data.get('refresh_token_expire_in')
    token_row.updated_at = datetime.utcnow()

    db.commit()

    app_token = create_access_token(subject=str(user.id))
    return OAuthExchangeResponse(
        access_token=app_token,
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            username=user.username,
            tiktokShopId=user.tiktok_open_id,
        ),
    )
