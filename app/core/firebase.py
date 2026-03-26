import logging

import httpx
import firebase_admin
from firebase_admin import auth as fb_auth

from app.core.exceptions import InvalidTokenException

logger = logging.getLogger(__name__)

_app: firebase_admin.App | None = None


def _get_app() -> firebase_admin.App:
    global _app
    if _app is None:
        from app.core.config import settings
        # Explicitly pass the GCP project ID so the SDK knows which Firebase
        # project to verify tokens against. Without this, Cloud Run's ADC
        # may not auto-detect the project correctly, causing aud/iss mismatches.
        _app = firebase_admin.initialize_app(
            options={"projectId": settings.gcp_project}
        )
        logger.info("Firebase Admin SDK initialised for project=%s", settings.gcp_project)
    return _app


def verify_firebase_token(id_token: str, expected_tenant_id: str) -> dict:
    """
    Verify a Firebase ID token issued by GCIP.

    Must use the tenant-scoped client — the module-level verify_id_token
    looks up users in the default namespace and fails for tenant users
    with "No user record found".
    """
    try:
        tenant_client = get_tenant_client(expected_tenant_id)
        # check_revoked=False: revocation check requires identitytoolkit.admin
        # IAM on the Cloud Run SA. Tokens expire naturally after 1 hour.
        decoded = tenant_client.verify_id_token(id_token, check_revoked=False)
    except fb_auth.RevokedIdTokenError:
        raise InvalidTokenException("Firebase token has been revoked")
    except fb_auth.ExpiredIdTokenError:
        raise InvalidTokenException("Firebase token has expired")
    except fb_auth.InvalidIdTokenError as exc:
        raise InvalidTokenException(f"Invalid Firebase token: {exc}")
    except Exception as exc:
        raise InvalidTokenException(f"Token verification failed: {exc}")

    return decoded


def get_tenant_client(tenant_id: str):
    """
    Return a tenant-scoped Firebase auth client (firebase-admin >= 7.x).

    In v7, TenantManager was removed.  The Client constructor now accepts
    ``tenant_id`` directly, and all operations on that client are tenant-scoped.
    """
    from firebase_admin._auth_client import Client as _AuthClient
    return _AuthClient(_get_app(), tenant_id=tenant_id)


async def send_invite_email(email: str, tenant_id: str, web_api_key: str) -> bool:
    """
    Send a Firebase password-reset (invite) email via the Identity Toolkit REST API.

    Uses the Web API Key (not the Admin SDK) because the Admin SDK's
    generate_password_reset_link only returns the link — it does not send email.

    Returns True on success, False if the API key is missing or the call fails.
    """
    if not web_api_key:
        logger.warning("FIREBASE_WEB_API_KEY not configured — invite email not sent to %s", email)
        return False

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={web_api_key}"
    payload = {
        "requestType": "PASSWORD_RESET",
        "email": email,
        "tenantId": tenant_id,
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=10.0)
        if resp.status_code == 200:
            logger.info("Invite email sent to %s", email)
            return True
        logger.warning(
            "Firebase invite email failed for %s: %s %s", email, resp.status_code, resp.text
        )
        return False
    except Exception as exc:
        logger.warning("Exception sending invite email to %s: %s", email, exc)
        return False
