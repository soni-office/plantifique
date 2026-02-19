from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import User
from app.utils.security import decode_access_token

router = APIRouter(prefix='/auth', tags=['Auth Session'])


def get_current_user(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Missing bearer token')

    token = authorization.replace('Bearer ', '', 1).strip()
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token')

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found')

    return user


@router.get('/me')
def me(user: User = Depends(get_current_user)):
    return {
        'id': str(user.id),
        'email': user.email,
        'username': user.username,
        'tiktokShopId': user.tiktok_open_id,
    }


@router.post('/logout', status_code=status.HTTP_204_NO_CONTENT)
def logout():
    return None
