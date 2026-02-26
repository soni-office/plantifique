from datetime import datetime, timezone
from app.repository.tiktok_token_repository import TikTokTokenRepository
from app.services.tiktok.oauth_service import TikTokOAuthService


class TokenService:

    def __init__(self, db):
        self.db = db
        self.repo = TikTokTokenRepository(db)

    # def get_valid_access_token(self, user_id: int):
    #     print("Getting valid access token for user_id=", user_id)
    #     token_row = self.repo.get_by_user_id(user_id)

    #     if not token_row:
    #         raise ValueError("Token not found")

    #     now = int(datetime.now(timezone.utc).timestamp())

    #     if now >= token_row.access_token_expire_in:
    #         new_data = TikTokOAuthService.refresh_access_token(
    #             token_row.refresh_token
    #         )

    #         token_row.access_token = new_data["access_token"]
    #         token_row.refresh_token = new_data["refresh_token"]
    #         token_row.access_token_expire_in = (
    #             now + new_data["access_token_expire_in"]
    #         )

    #         self.db.commit()

    #     return token_row.access_token

    from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
from app.repository.tiktok_token_repository import TikTokTokenRepository
from app.services.tiktok.oauth_service import TikTokOAuthService


class TokenService:

    def __init__(self, db):
        self.db = db
        self.repo = TikTokTokenRepository(db)

    def get_valid_access_token(self, user_id: int) -> str:
        print(f"[TokenService] Fetching token for user_id={user_id}")

        token_row = self.repo.get_by_user_id(user_id)

        if not token_row:
            raise ValueError("TikTok token not found. Please login again.")

        now = int(datetime.now(timezone.utc).timestamp())

        # 🔹 Safety buffer (refresh 60 seconds before expiry)
        buffer_seconds = 60

        is_expired = now >= (token_row.access_token_expire_in - buffer_seconds)

        if not is_expired:
            return token_row.access_token

        print("[TokenService] Access token expired. Refreshing...")

        try:
            new_data = TikTokOAuthService.refresh_access_token(
                token_row.refresh_token
            )

            new_access_token = new_data["access_token"]
            new_refresh_token = new_data.get("refresh_token", token_row.refresh_token)
            expires_in = new_data["access_token_expire_in"]

            token_row.access_token = new_access_token
            token_row.refresh_token = new_refresh_token
            token_row.access_token_expire_in = now + expires_in

            self.db.commit()

            print("[TokenService] Token refreshed successfully")

            return new_access_token

        except Exception as e:
            self.db.rollback()
            print("[TokenService] Token refresh failed:", str(e))
            raise ValueError("Failed to refresh TikTok token. Please re-authenticate.")