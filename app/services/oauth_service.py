"""
TikTok Shop OAuth flow — state management, code exchange, token persistence.
"""
import secrets
import logging

from app.clients.tiktok.oauth_client import TikTokOAuthClient
from app.repository.oauth_state_repository import OAuthStateRepository
from app.repository.access_token_repository import AccessTokenRepository
from app.core.config import settings

logger = logging.getLogger(__name__)


class OAuthService:

    def __init__(self):
        self.state_repo = OAuthStateRepository()
        self.token_repo = AccessTokenRepository()

    def get_status(self, org_id: str) -> dict:
        """Return whether the org has an active TikTok Shop token."""
        token = self.token_repo.get_by_org(org_id)
        connected = token is not None and token.get("status") == "ACTIVE"
        return {"connected": connected}

    def get_connect_url(self, org_id: str, issued_by: str) -> str:
        """
        Generate a TikTok OAuth URL and persist the state token for CSRF protection.
        Returns the auth URL the frontend should redirect the browser to.
        """
        state = secrets.token_urlsafe(32)
        self.state_repo.create(state=state, org_id=org_id, issued_by=issued_by)
        auth_url = TikTokOAuthClient.get_auth_url(state)
        logger.info("TikTok connect initiated org_id=%s issued_by=%s", org_id, issued_by)
        return auth_url

    def handle_callback(self, code: str, state: str) -> str:
        """
        Exchange the auth code for tokens and persist them at org level.
        Returns the frontend redirect URL with a success signal.
        Raises ValueError on invalid/expired state or token exchange failure.
        """
        state_doc = self.state_repo.get_by_state(state)
        if not state_doc:
            raise ValueError("Invalid or expired OAuth state")

        # Consume the single-use state token immediately
        self.state_repo.delete(state)

        org_id = state_doc["org_id"]
        issued_by = state_doc["issued_by"]

        token_data = TikTokOAuthClient.exchange_code(code)

        self.token_repo.upsert(
            org_id=org_id,
            issued_by=issued_by,
            tiktok_open_id=token_data.get("open_id"),
            access_token=token_data["access_token"],
            refresh_token=token_data["refresh_token"],
            access_token_expires_at=int(token_data.get("access_token_expire_in")),
            refresh_token_expires_at=(
                int(token_data["refresh_token_expire_in"])
                if token_data.get("refresh_token_expire_in")
                else None
            ),
        )

        logger.info(
            "TikTok org-level token saved org_id=%s issued_by=%s open_id=%s",
            org_id, issued_by, token_data.get("open_id"),
        )
        return f"{settings.frontend_url.rstrip('/')}/auth/tiktokshop/callback?tiktok_connected=true"

    def revoke(self, org_id: str) -> None:
        """Mark the org's TikTok token as REVOKED."""
        self.token_repo.revoke(org_id)
        logger.info("TikTok token revoked org_id=%s", org_id)
