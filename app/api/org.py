import logging
import re

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.api.auth_session import require_role
from app.repository.org_repository import OrgRepository
from fastapi import Depends

router = APIRouter(prefix="/orgs", tags=["Organisations"])
logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r'^[a-z0-9_-]{2,64}$')


class CreateOrgBody(BaseModel):
    name: str
    org_id: str = ""   # optional slug; auto-generated from name if omitted


def _slugify(name: str) -> str:
    """Turn 'Acme Corp' → 'acme_corp' as a default org_id."""
    slug = re.sub(r'[^a-z0-9]+', '_', name.lower().strip()).strip('_')
    return slug[:64] or "org"


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_org(
    body: CreateOrgBody,
    _caller=Depends(require_role("SUPER_ADMIN")),
):
    """
    Create a new organisation record.  SUPER_ADMIN only.

    ``org_id`` is used as the Firestore document ID and as the claim value
    stored in every user's ID token.  If omitted, it is derived from ``name``.
    """
    if not body.name.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "name is required")

    org_id = body.org_id.strip() or _slugify(body.name)

    if not _SLUG_RE.match(org_id):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "org_id must be 2-64 chars, lowercase letters / digits / _ / -",
        )

    repo = OrgRepository()
    if repo.get_by_id(org_id):
        raise HTTPException(status.HTTP_409_CONFLICT, f"org_id '{org_id}' already exists")

    org = repo.create(name=body.name.strip(), org_id=org_id)
    logger.info("Org created org_id=%s name=%s", org_id, body.name)
    return org


@router.get("")
async def list_orgs(
    _caller=Depends(require_role("SUPER_ADMIN")),
):
    """List all active organisations.  SUPER_ADMIN only."""
    orgs = OrgRepository().get_all()
    return {"orgs": orgs}
