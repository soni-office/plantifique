import os

class Settings:
    TIKTOK_APP_KEY = os.getenv("TIKTOK_APP_KEY")
    TIKTOK_ACCESS_TOKEN = os.getenv("TIKTOK_ACCESS_TOKEN")
    TIKTOK_APP_SECRET = os.getenv("TIKTOK_APP_SECRET")

    def generate_tiktok_sign(self, params: dict) -> str:
        """
        TikTok signature logic goes here.
        (HMAC / SHA256 as per TikTok docs)
        """
        # TODO: implement official signing
        return "mocked-sign"

settings = Settings()
