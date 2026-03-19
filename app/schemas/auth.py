from typing import Optional
from pydantic import BaseModel


class OAuthExchangeRequest(BaseModel):
    code: str
    state: Optional[str] = None


class StandardEmailLoginRequest(BaseModel):
    email: str


class UserResponse(BaseModel):
    id: str
    email: str | None = None
    username: str | None = None
    tiktokShopId: str | None = None  # Make optional as it's not set for email login


class SessionResponse(BaseModel):
    jwt_token: str
    token_type: str = 'Bearer'
    user: UserResponse


class OAuthExchangeResponse(BaseModel):
    jwt_token: str
    token_type: str = 'Bearer'
    user: UserResponse
