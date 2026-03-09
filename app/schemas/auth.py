from typing import Optional
from pydantic import BaseModel


class OAuthExchangeRequest(BaseModel):
    code: str
    state: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str | None = None
    username: str | None = None
    tiktokShopId: str


class OAuthExchangeResponse(BaseModel):
    jwt_token: str
    token_type: str = 'Bearer'
    user: UserResponse
