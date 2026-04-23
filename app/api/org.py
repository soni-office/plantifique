import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.auth_session import require_role
from app.services.org_service import OrgService, get_org_service

router = APIRouter(prefix="/orgs", tags=["Organisations"])
logger = logging.getLogger(__name__)


class CreateOrgBody(BaseModel):
    name: str
    org_id: str = ""


@router.post("", status_code=status.HTTP_201_CREATED)
def create_org(
    body: CreateOrgBody,
    _caller=Depends(require_role("SUPER_ADMIN")),
    svc: OrgService = Depends(get_org_service),
):
    """Create a new organisation. SUPER_ADMIN only."""
    try:
        return svc.create(name=body.name, org_id=body.org_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except LookupError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


@router.get("")
async def list_orgs(
    _caller=Depends(require_role("SUPER_ADMIN")),
    svc: OrgService = Depends(get_org_service),
):
    """List all active organisations. SUPER_ADMIN only."""
    return {"orgs": await svc.list_all()}
