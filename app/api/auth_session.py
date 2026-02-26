

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
import logging
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.db.database import get_db
from app.repository.user_repository import UserRepository
from app.core.security import decode_access_token

router = APIRouter(prefix="/auth", tags=["Auth Session"])

logger = logging.getLogger(__name__)


# def get_current_user(
#     db: Session = Depends(get_db),
#     authorization: str | None = Header(default=None, alias="Authorization"),
# ):
#     if not authorization or not authorization.startswith("Bearer "):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Missing bearer token",
#         )

#     token = authorization.replace("Bearer ", "", 1).strip()
#     user_id = decode_access_token(token)

#     user_repo = UserRepository(db)
#     user = user_repo.get_by_id(int(user_id))

#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="User not found",
#         )

#     return user

security = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    token = credentials.credentials

    user_id = decode_access_token(token)

    user_repo = UserRepository(db)
    user = user_repo.get_by_id(int(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user

@router.get("/me")
async def me(user=Depends(get_current_user)):
    logger.info("Fetching session details for user_id=%s", user.id)

    return {
        "id": str(user.id),
        "email": user.email,
        "username": user.username,
        "tiktokShopId": user.tiktok_open_id,
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout():
    logger.info("User logout requested")
    return None