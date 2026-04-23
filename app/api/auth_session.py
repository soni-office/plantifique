import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import InvalidTokenException
from app.core.firebase import get_tenant_client, send_invite_email, verify_firebase_token
from app.repository.user_repository import UserRepository

router = APIRouter(prefix="/auth", tags=["Auth Session"])
logger = logging.getLogger(__name__)
security = HTTPBearer()

_user_repo = UserRepository()


# Auth dependency — stateless, zero DB calls

def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Verify the Firebase ID token and return the caller's identity from claims.
    Role and org_id are stored as GCIP custom claims — no Firestore lookup needed.

    SUPER_ADMIN org override: if the request carries an ``X-Active-Org`` header,
    and the caller is a SUPER_ADMIN, that value replaces the token's own org_id.
    This lets the super-admin operate in the context of any org without re-issuing tokens.
    """
    try:
        decoded = verify_firebase_token(
            credentials.credentials,
            expected_tenant_id=settings.firebase_tenant_id,
        )
    except InvalidTokenException as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    role = decoded.get("role", "ORG_MEMBER")
    org_id = decoded.get("org_id", "")

    # Allow SUPER_ADMIN to impersonate any org via X-Active-Org header
    if role == "SUPER_ADMIN":
        active_org = request.headers.get("X-Active-Org", "").strip()
        if active_org:
            org_id = active_org

    return {
        "uid": decoded["uid"],
        "id": decoded["uid"],          # backwards-compat alias used by other routers
        "org_id": org_id,
        "role": role,
        "email": decoded.get("email", ""),
    }


def require_role(*allowed_roles: str):
    """Dependency factory — gates an endpoint to specific roles."""
    def _check(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of: {list(allowed_roles)}",
            )
        return user
    return _check


# Request bodies

class InviteBody(BaseModel):
    email: str
    name: str = ""
    role: str = "ORG_MEMBER"   # ORG_MEMBER | ORG_ADMIN | SUPER_ADMIN
    org_id: str = ""            # SUPER_ADMIN only — ignored for ORG_ADMIN callers


class SetRoleBody(BaseModel):
    uid: str
    role: str


# Endpoints

@router.get("/me")
async def me(user: dict = Depends(get_current_user)):
    """Return the current user's profile (claims + Firestore metadata)."""
    db_user = _user_repo.get_by_id(user["uid"])
    return {
        "uid": user["uid"],
        "email": db_user.get("email") if db_user else user["email"],
        "name": db_user.get("name") if db_user else None,
        "org_id": user["org_id"],
        "role": user["role"],
    }


@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def invite_user(
    body: InviteBody,
    caller: dict = Depends(get_current_user),
):
    """
    Create a GCIP user in the tenant and send them a password-reset (invite) link.

    Role rules:
    - SUPER_ADMIN → can invite anyone with any role to any org.
    - ORG_ADMIN   → can only invite ORG_MEMBERs, always into their own org.
    - ORG_MEMBER  → 403.
    """
    caller_role = caller["role"]

    if caller_role == "ORG_MEMBER":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions to invite users")

    if caller_role == "ORG_ADMIN":
        if body.role in ("ORG_ADMIN", "SUPER_ADMIN"):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "ORG_ADMIN can only invite ORG_MEMBERs",
            )
        target_org = caller["org_id"]   # force to caller's own org
    else:  # SUPER_ADMIN
        target_org = body.org_id or caller["org_id"]

    tenant_client = get_tenant_client(settings.firebase_tenant_id)

    try:
        gcip_user = tenant_client.create_user(
            email=body.email,
            display_name=body.name or body.email,
            email_verified=False,
        )
    except Exception as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Failed to create GCIP user: {exc}")

    # Store role + org as custom claims (carried in every ID token — no DB hit on auth)
    tenant_client.set_custom_user_claims(gcip_user.uid, {
        "role": body.role,
        "org_id": target_org,
    })

    # Mirror metadata to Firestore so org-level queries still work
    _user_repo.create(
        uid=gcip_user.uid,
        org_id=target_org,
        email=body.email,
        name=body.name,
        role=body.role,
    )

    # Try to send the invite email via Firebase REST API.
    # Falls back to returning the link if something goes wrong.
    email_sent = await send_invite_email(
        email=body.email,
        tenant_id=settings.firebase_tenant_id,
        web_api_key=settings.firebase_web_api_key,
    )

    # Generate the password-reset link as a fallback (useful when email not sent)
    invite_link: str | None = None
    if not email_sent:
        try:
            invite_link = tenant_client.generate_password_reset_link(body.email)
        except Exception as exc:
            logger.warning("Could not generate invite link for %s: %s", body.email, exc)

    logger.info(
        "User invited uid=%s email=%s org=%s role=%s by=%s email_sent=%s",
        gcip_user.uid, body.email, target_org, body.role, caller["uid"], email_sent,
    )

    return {
        "uid": gcip_user.uid,
        "email": body.email,
        "org_id": target_org,
        "role": body.role,
        "email_sent": email_sent,
        "invite_link": invite_link,  # None when email was sent successfully
    }


@router.get("/users")
async def list_users(
    caller: dict = Depends(require_role("ORG_ADMIN", "SUPER_ADMIN")),
):
    """List all active users in the caller's org."""
    members = _user_repo.get_all_by_org(caller["org_id"])
    return {"users": members}


@router.delete("/users/{uid}", status_code=200)
async def remove_user(
    uid: str,
    caller: dict = Depends(require_role("ORG_ADMIN", "SUPER_ADMIN")),
):
    """
    Remove a user from the org.

    - Deletes the GCIP account (prevents further login).
    - Sets Firestore status to DEACTIVATED (preserves audit trail).

    Role rules:
    - SUPER_ADMIN → can remove ORG_ADMIN and ORG_MEMBER.
    - ORG_ADMIN   → can only remove ORG_MEMBER.
    - Neither role can remove themselves.
    """
    if uid == caller["uid"]:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot remove yourself")

    target = _user_repo.get_by_id(uid)
    if not target or target.get("status") != "ACTIVE":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    # Ensure target belongs to caller's org but this should be passed if the caller is SUPER_ADMIN (who can remove users from any org)
    if target.get("org_id") != caller["org_id"] and caller["role"] != "SUPER_ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User does not belong to your org")

    # ORG_ADMIN cannot remove another admin or super admin
    target_role = target.get("role", "ORG_MEMBER")
    if caller["role"] == "ORG_ADMIN" and target_role in ("ORG_ADMIN", "SUPER_ADMIN"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "ORG_ADMIN can only remove ORG_MEMBERs")

    # Delete from GCIP (hard delete — user can no longer log in)
    tenant_client = get_tenant_client(settings.firebase_tenant_id)
    try:
        tenant_client.delete_user(uid)
    except Exception as exc:
        logger.warning("GCIP delete failed for uid=%s: %s — continuing with Firestore update", uid, exc)

    # Soft-delete in Firestore (keeps audit trail)
    _user_repo.update_status(uid, "DEACTIVATED")

    logger.info("User removed uid=%s by=%s org=%s", uid, caller["uid"], caller["org_id"])
    return {"removed": True, "uid": uid}


@router.post("/set-role")
async def set_role(
    body: SetRoleBody,
    caller: dict = Depends(require_role("SUPER_ADMIN", "ORG_ADMIN")),
):
    """
    Update a user's role in GCIP custom claims + Firestore mirror.

    - SUPER_ADMIN: can set any role.
    - ORG_ADMIN:   cannot elevate to ORG_ADMIN or SUPER_ADMIN.
    """
    if caller["role"] == "ORG_ADMIN" and body.role in ("ORG_ADMIN", "SUPER_ADMIN"):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "ORG_ADMIN cannot assign ORG_ADMIN or SUPER_ADMIN roles",
        )

    tenant_client = get_tenant_client(settings.firebase_tenant_id)

    try:
        gcip_user = tenant_client.get_user(body.uid)
    except Exception:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found in GCIP")

    existing_claims = gcip_user.custom_claims or {}
    tenant_client.set_custom_user_claims(body.uid, {**existing_claims, "role": body.role})

    # Update Firestore mirror
    _user_repo.col.document(body.uid).update({"role": body.role})

    logger.info("Role updated uid=%s role=%s by=%s", body.uid, body.role, caller["uid"])
    return {"uid": body.uid, "role": body.role}
