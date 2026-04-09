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
# curl -X GET \
#  'https://open-api.tiktokglobalshop.com/affiliate_seller/202512/sample_applications/deeplink?collaboration_id=710240393&sign=5361235029d141222525e303d742f9e38aea052d10896d3197ab9d6233730b8c&timestamp=1623812664&shop_cipher=GCP_XF90igAAAABh00qsWgtvOiGFNqyubMt3&product_id=123456&sku_id=123456&campaign_id=3939495&valid_days=14&app_key=38abcd' \
# -H 'x-tts-access-token: TTP_pwSm2AAAAABmmtFz1xlyKMnwg74T2GJ5s0uQbS8jPjb_GkdFVCxPqzQXSyuyfXdQa0AqyDsea2tYFNVf4XeqgZHFfPyv0Vs659QqyLYfsGzanZ5XZAin3_ZkcIxxS0_In6u6XDeU96k' \
# -H 'content-type: application/json'