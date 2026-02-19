from pydantic import BaseModel


class OAuthExchangeRequest(BaseModel):
    code: str
    state: str


class UserResponse(BaseModel):
    id: str
    email: str | None = None
    username: str | None = None
    tiktokShopId: str


class OAuthExchangeResponse(BaseModel):
    access_token: str
    token_type: str = 'Bearer'
    user: UserResponse
