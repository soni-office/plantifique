from datetime import datetime, timezone
from app.repository.access_token_repository import AccessTokenRepository
from app.services.tiktok.oauth_service import TikTokOAuthService


class TokenService:
    """
     Provides a valid TikTok access token for a given org.
    """

    def __init__(self):
        self.repo = AccessTokenRepository()

    def get_valid_access_token(self, org_id: str) -> str:
        """
        Return a guaranteed-valid TikTok access token for the org.
        Raises ValueError if token is missing or refresh fails.
        """
        token_row = self.repo.get_by_org(org_id)

        if not token_row:
            raise ValueError(
                f"No TikTok token found for org_id={org_id}. "
                "The admin must complete TikTok OAuth first."
            )

        if token_row.get("status") == "REVOKED":
            raise ValueError(
                f"TikTok token for org_id={org_id} has been revoked. "
                "Please re-authenticate."
            )

        now = int(datetime.now(timezone.utc).timestamp())

        # Safety buffer: treat token as expired 60s before actual expiry
        buffer_seconds = 120
        expires_at = token_row.get("access_token_expires_at", 0)
        is_expired = now >= (expires_at - buffer_seconds)

        # Happy path: token is still valid — return immediately
        if not is_expired:
            return token_row["access_token"]
        # Token is expired — perform silent background refresh
        print(f"[TokenService] Access token expired for org_id={org_id}. Refreshing...")
        try:
            new_data = TikTokOAuthService.refresh_access_token(
                token_row["refresh_token"]
            )

            new_access_token = new_data["access_token"]
            new_refresh_token = new_data.get(
                "refresh_token", token_row["refresh_token"]
            )
            new_access_token_expires_at = new_data["access_token_expire_in"]
            new_refresh_token_expires_at = new_data["refresh_token_expire_in"]

            self.repo.update_tokens(org_id, {
                "access_token": new_access_token,
                "refresh_token": new_refresh_token,
                "access_token_expires_at": new_access_token_expires_at,
                "refresh_token_expires_at": new_refresh_token_expires_at,
            })

            print(f"[TokenService] Token refreshed successfully for org_id={org_id}")
            return new_access_token

        except Exception as e:
            print(f"[TokenService] Token refresh failed for org_id={org_id}: {e}")
            raise ValueError(
                "Failed to refresh TikTok token. "
                "Please ask the admin to re-authenticate via TikTok."
            )