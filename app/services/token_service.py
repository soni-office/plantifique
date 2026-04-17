"""
Provides a valid TikTok access token for an org, refreshing silently when expired.
"""
import logging
from datetime import datetime, timezone

from app.repository.access_token_repository import AccessTokenRepository
from app.clients.tiktok.oauth_client import TikTokOAuthClient

logger = logging.getLogger(__name__)

_EXPIRY_BUFFER_SECONDS = 120


class TokenService:

    def __init__(self):
        self.repo = AccessTokenRepository()

    def get_valid_access_token(self, org_id: str) -> str:
        """
        Return a guaranteed-valid TikTok access token for the org.
        Raises ValueError if the token is missing, revoked, or refresh fails.
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
        expires_at = token_row.get("access_token_expires_at", 0)

        if now < (expires_at - _EXPIRY_BUFFER_SECONDS):
            return token_row["access_token"]

        # Token expired — silent refresh
        logger.info("Access token expired for org_id=%s, refreshing...", org_id)
        try:
            new_data = TikTokOAuthClient.refresh_token(token_row["refresh_token"])
            self.repo.update_tokens(org_id, {
                "access_token": new_data["access_token"],
                "refresh_token": new_data.get("refresh_token", token_row["refresh_token"]),
                "access_token_expires_at": new_data["access_token_expire_in"],
                "refresh_token_expires_at": new_data["refresh_token_expire_in"],
            })
            logger.info("Token refreshed successfully for org_id=%s", org_id)
            return new_data["access_token"]
        except Exception as e:
            logger.error("Token refresh failed for org_id=%s: %s", org_id, e)
            raise ValueError(
                "Failed to refresh TikTok token. "
                "Please ask the admin to re-authenticate via TikTok."
            )
