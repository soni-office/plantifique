from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from app.core.config import settings
from app.core.exceptions import InvalidTokenException


def create_jwt_token(user_id: str, tiktok_open_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_exp_minutes)
    payload = {
        "sub": user_id,
        "tiktok_id": tiktok_open_id,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_jwt_token(jwt_token: str) -> dict:
    try:
        payload = jwt.decode(
            jwt_token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return {
            "user_id": payload["sub"],
            "tiktok_id": payload.get("tiktok_id", ""),
        }
    except JWTError:
        raise InvalidTokenException("Invalid or expired token")