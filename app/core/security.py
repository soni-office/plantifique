from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from app.core.config import settings
from app.core.exceptions import InvalidTokenException


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_exp_minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload["sub"]
    except JWTError:
        raise InvalidTokenException("Invalid or expired token")