from datetime import datetime, timezone
from app.repository.tiktok_token_repository import TikTokTokenRepository
from app.services.tiktok.oauth_service import TikTokOAuthService


class TokenService:

    def __init__(self):
        self.repo = TikTokTokenRepository()

    def get_valid_access_token(self, user_id: str) -> str:
        print(f"[TokenService] Fetching token for user_id={user_id}")

        token_row = self.repo.get_by_user_id(user_id)

        if not token_row:
            raise ValueError("TikTok token not found. Please login again.")

        now = int(datetime.now(timezone.utc).timestamp())

        # Safety buffer: refresh 60 seconds before actual expiry
        buffer_seconds = 60
        is_expired = now >= (token_row["access_token_expire_in"] - buffer_seconds)

        # Happy path: token is still valid, return immediately
        if not is_expired:
            return token_row["access_token"]

        # Token is expired — only now do the heavy refresh work
        print("[TokenService] Access token expired. Refreshing...")
        try:
            new_data = TikTokOAuthService.refresh_access_token(
                token_row["refresh_token"]
            )

            new_access_token = new_data["access_token"]
            new_refresh_token = new_data.get("refresh_token", token_row["refresh_token"])
            new_expire_in = now + new_data["access_token_expire_in"]

            self.repo.update(token_row["id"], {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "access_token_expire_in": new_expire_in,
            })

            print("[TokenService] Token refreshed successfully")
            return new_access_token

        except Exception as e:
            print("[TokenService] Token refresh failed:", str(e))
            raise ValueError("Failed to refresh TikTok token. Please re-authenticate.")