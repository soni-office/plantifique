import os
from dataclasses import dataclass
from typing import List

from dotenv import load_dotenv

# Load .env file for local development.
# In Cloud Run, env vars are injected directly — dotenv is a no-op there.
load_dotenv()


@dataclass(frozen=True)
class Settings:
    # -------------------------------------------------------------------------
    # Environment
    # -------------------------------------------------------------------------
    env: str = os.getenv('ENV', 'dev')   # 'dev' | 'prod'

    # -------------------------------------------------------------------------
    # GCP
    # -------------------------------------------------------------------------
    gcp_project: str = os.getenv('GCP_PROJECT', 'tiktok-ai-agent-488417')
    # Explicit override — otherwise derived from env via firestore_db property
    firestore_database: str = os.getenv('FIRESTORE_DATABASE', '')

    # -------------------------------------------------------------------------
    # Organisation
    # -------------------------------------------------------------------------
    org_id: str = os.getenv('ORG_ID', 'org_plantifique')

    # -------------------------------------------------------------------------
    # Auth / JWT
    # -------------------------------------------------------------------------
    jwt_secret_key: str = os.getenv('JWT_SECRET_KEY', 'change_me_in_env')
    jwt_algorithm: str = os.getenv('JWT_ALGORITHM', 'HS256')
    jwt_exp_minutes: int = int(os.getenv('JWT_EXP_MINUTES', '60'))

    # -------------------------------------------------------------------------
    # TikTok OAuth
    # -------------------------------------------------------------------------
    app_key: str = os.getenv('APP_KEY', '')
    app_secret: str = os.getenv('APP_SECRET', '')
    redirect_uri: str = os.getenv('REDIRECT_URI', 'http://localhost:8000/auth/tiktokshop/callback')
    auth_url: str = os.getenv('AUTH_URL', 'https://auth.tiktok-shops.com/oauth/authorize')
    token_url: str = os.getenv('TOKEN_URL', 'https://auth.tiktok-shops.com/api/v2/token/get')
    refresh_token_url: str = os.getenv('REFRESH_TOKEN_URL', 'https://auth.tiktok-shops.com/api/v2/token/refresh')
    base_url: str = 'https://open-api.tiktokglobalshop.com'
    mock_tiktok: bool = os.getenv('MOCK_TIKTOK', 'false').lower() == 'true'
    # Sample requests are not yet granted API access — keep them mocked independently
    mock_sample_requests: bool = os.getenv('MOCK_SAMPLE_REQUESTS', 'true').lower() == 'true'

    # -------------------------------------------------------------------------
    # Frontend / CORS
    # -------------------------------------------------------------------------
    # Primary frontend origin — drives the TikTok OAuth redirect and CORS list.
    # Dev: http://localhost:5173  |  Prod: https://<firebase-project>.web.app
    frontend_url: str = os.getenv('FRONTEND_URL', 'http://localhost:5173')
    frontend_oauth_callback_path: str = os.getenv('FRONTEND_OAUTH_CALLBACK_PATH', '/auth/tiktokshop/callback')
    # Optional extra origins (comma-separated, e.g. the *.firebaseapp.com alias in prod)
    extra_cors_origins: str = os.getenv('EXTRA_CORS_ORIGINS', '')

    # -------------------------------------------------------------------------
    # LLM / MiniMax
    # -------------------------------------------------------------------------
    # minmax_api_key: str = os.getenv('minmax_api_key', '')
    # minmax_base_url: str = os.getenv('MINIMAX_BASE_URL', 'https://api.minimax.chat/v1')

    # -------------------------------------------------------------------------
    # Token encryption
    # -------------------------------------------------------------------------
    tiktok_token_encryption_key: str = os.getenv('TIKTOK_TOKEN_ENCRYPTION_KEY', '')

    # -------------------------------------------------------------------------
    # TikTok API paths
    # -------------------------------------------------------------------------
    creator_search_path: str = os.getenv(
        'CREATOR_SEARCH_PATH',
        '/affiliate_seller/202508/marketplace_creators/search',
    )
    creator_detail_path: str = os.getenv(
        'CREATOR_DETAIL_PATH',
        '/affiliate_seller/202508/marketplace_creators/{creator_user_id}',
    )
    product_search_path: str = os.getenv(
        'PRODUCT_SEARCH_PATH',
        '/affiliate_seller/202508/marketplace_products/search',
    )

    # -------------------------------------------------------------------------
    # Automation / Internal Scheduler
    # -------------------------------------------------------------------------
    # Shared secret between Cloud Scheduler and the /internal/* endpoints.
    # Store in GCP Secret Manager — never commit this value.
    internal_api_secret: str = os.getenv('INTERNAL_API_SECRET', '')

    # -------------------------------------------------------------------------
    # Google Cloud Identity Platform (GCIP) — multi-tenant auth
    # -------------------------------------------------------------------------
    # Tenant ID from the Identity Platform console.
    # dev → teampop-6fiht  |  prod → set via FIREBASE_TENANT_ID env var
    firebase_tenant_id: str = os.getenv('FIREBASE_TENANT_ID', 'teampop-6fiht')
    # Web API Key — used by the REST-based invite email sender.
    # Found in Firebase console → Project Settings → General → Web API Key.
    firebase_web_api_key: str = os.getenv('FIREBASE_WEB_API_KEY', '')

    # -------------------------------------------------------------------------
    # RAG
    # -------------------------------------------------------------------------
    want_to_use_rag: bool = os.getenv('WANT_TO_USE_RAG', 'false').lower() == 'true'

    # -------------------------------------------------------------------------
    # Vertex AI
    # -------------------------------------------------------------------------
    vertex_model: str = os.getenv('VERTEX_MODEL', 'gemini-2.5-flash')

    # Redis credentials
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    CACHE_DEFAULT_TTL: int = int(os.getenv("CACHE_DEFAULT_TTL", 300))
    
    # TikAPI (creator video & profile enrichment)
    tikapi_key: str = os.getenv('TIKAPI_KEY', '')

    # -------------------------------------------------------------------------
    # Computed properties
    # -------------------------------------------------------------------------
    @property
    def firestore_db(self) -> str:
        """Firestore database ID. Explicit FIRESTORE_DATABASE override or auto-derived from ENV."""
        if self.firestore_database:
            return self.firestore_database
        return f'plantifique-pop-{self.env}'

    @property
    def allowed_origins(self) -> List[str]:
        """CORS allowed origins. Always includes localhost for local dev."""
        origins = [
            'http://localhost:5173',
            'http://127.0.0.1:5173',
        ]
        if self.frontend_url and self.frontend_url not in origins:
            origins.append(self.frontend_url)
        if self.extra_cors_origins:
            for origin in self.extra_cors_origins.split(','):
                o = origin.strip()
                if o and o not in origins:
                    origins.append(o)
        return origins

    @property
    def is_production(self) -> bool:
        return self.env == 'prod'


settings = Settings()
