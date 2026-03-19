from fastapi import APIRouter, Depends, status, HTTPException
import logging
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.security import decode_jwt_token, create_jwt_token
from app.repository.user_repository import UserRepository
from app.schemas.auth import StandardEmailLoginRequest

router = APIRouter(prefix="/auth", tags=["Auth Session"])

logger = logging.getLogger(__name__)

security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Stateless authentication: decode the JWT and return full user context
    directly from the token payload — zero database calls required.
    """
    jwt_token = credentials.credentials
    payload = decode_jwt_token(jwt_token)

    return {
        "id": payload["user_id"],
        "org_id": payload["org_id"],
        "role": payload["role"],
        "tiktok_open_id": payload["tiktok_id"],
    }


@router.get("/me")
async def me(user=Depends(get_current_user)):
    logger.info(
        "Fetching session details for user_id=%s org_id=%s role=%s",
        user["id"],
        user["org_id"],
        user["role"],
    )
    # Fetch full user record from Firestore to include email, name, username
    user_repo = UserRepository()
    db_user = user_repo.get_by_id(user["id"])

    return {
        "id": user["id"],
        "email": db_user.get("email") if db_user else None,
        "name": db_user.get("name") if db_user else None,
        "username": db_user.get("username") if db_user else None,
        "org_id": user["org_id"],
        "role": user["role"],
        "tiktokShopId": user["tiktok_open_id"],
    }


@router.post("/login")
async def email_login(payload: StandardEmailLoginRequest):
    """
    Standard login for team members.
    """
    user_repo = UserRepository()
    user = user_repo.get_by_email(payload.email)

    if not user:
        logger.warning("Unrecognized login attempt: %s", payload.email)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found. Please ask your Admin for an invite.",
        )

    # Issue app JWT with full organizational context
    jwt_token = create_jwt_token(
        user_id=user["id"],
        org_id=user["org_id"],
        role=user.get("role", "ORG_MEMBER"),
        tiktok_open_id=user.get("tiktok_open_id") or "",
    )

    return {
        "jwt_token": jwt_token,
        "token_type": "Bearer",
        "user": {
            "id": user["id"],
            "email": user.get("email"),
            "role": user.get("role", "ORG_MEMBER"),
            "org_id": user["org_id"],
            "tiktokShopId": user.get("tiktok_open_id"),
        },
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout():
    """Client-side logout — JWT is stateless so no server action is needed."""
    logger.info("User logout requested")
    return None