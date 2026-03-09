from fastapi import APIRouter, Depends, status
import logging
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import decode_jwt_token

router = APIRouter(prefix="/auth", tags=["Auth Session"])

logger = logging.getLogger(__name__)

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Stateless authentication: decode the JWT and return user info directly
    from the token payload — no database call required.
    """
    jwt_token = credentials.credentials
    payload = decode_jwt_token(jwt_token)

    # Return a simple dict built entirely from the token — zero DB queries
    return {
        "id": payload["user_id"],
        "tiktok_open_id": payload["tiktok_id"],
    }


@router.get("/me")
async def me(user=Depends(get_current_user)):
    logger.info("Fetching session details for user_id=%s", user["id"])

    return {
        "id": user["id"],
        "tiktokShopId": user["tiktok_open_id"],
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout():
    logger.info("User logout requested")
    return None