import logging

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

logger = logging.getLogger(__name__)


class TokenCrypto:
    """
    Encrypts/decrypts TikTok tokens at rest when TIKTOK_TOKEN_ENCRYPTION_KEY
    is configured. If key is missing or invalid, methods gracefully fall back
    to plaintext mode to avoid breaking existing environments.
    """

    def __init__(self):
        self._fernet = None
        key = settings.tiktok_token_encryption_key.strip()
        if not key:
            return
        try:
            self._fernet = Fernet(key.encode("utf-8"))
        except Exception:
            logger.exception(
                "Invalid TIKTOK_TOKEN_ENCRYPTION_KEY. "
                "Token encryption disabled; values will be stored plaintext."
            )

    @property
    def enabled(self) -> bool:
        return self._fernet is not None

    def encrypt(self, value: str | None) -> str | None:
        if value is None or not self._fernet:
            return value
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str | None) -> str | None:
        if value is None or not self._fernet:
            return value
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            # Supports mixed old/new data by returning plaintext when token
            # wasn't encrypted with the configured key.
            return value
