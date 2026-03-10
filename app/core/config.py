import os
from dataclasses import dataclass

from dotenv import load_dotenv
load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        'DATABASE_URL',
        'postgresql+psycopg://postgres:postgres@localhost:5432/plantifique',
    )
    jwt_secret_key: str = os.getenv('JWT_SECRET_KEY', 'change_me_in_env')
    jwt_algorithm: str = os.getenv('JWT_ALGORITHM', 'HS256')
    jwt_exp_minutes: int = int(os.getenv('JWT_EXP_MINUTES', '60'))
    app_key: str = os.getenv('APP_KEY', '')
    app_secret: str = os.getenv('APP_SECRET', '')
    redirect_uri: str = os.getenv('REDIRECT_URI', 'http://localhost:8000/auth/tiktokshop/callback')
    auth_url: str = os.getenv('AUTH_URL', 'https://auth.tiktok-shops.com/oauth/authorize')
    token_url: str = os.getenv('TOKEN_URL', 'https://auth.tiktok-shops.com/api/v2/token/get')

    frontend_url: str = os.getenv('FRONTEND_URL', 'http://localhost:5173')
    frontend_oauth_callback_path: str = os.getenv('FRONTEND_OAUTH_CALLBACK_PATH', '/auth/tiktokshop/callback')
    base_url = "https://open-api.tiktokglobalshop.com"
    mock_tiktok: bool = True
    minmax_api_key : str = os.getenv('minmax_api_key', '')
    minmax_base_url: str = os.getenv('MINIMAX_BASE_URL', 'https://api.minimax.chat/v1')
    tiktok_token_encryption_key: str = os.getenv('TIKTOK_TOKEN_ENCRYPTION_KEY', '')
    creator_search_path: str = os.getenv('CREATOR_SEARCH_PATH', '/affiliate_seller/202508/marketplace_creators/search')
    product_search_path: str = os.getenv('PRODUCT_SEARCH_PATH', '/affiliate_seller/202508/marketplace_products/search')

settings = Settings()
