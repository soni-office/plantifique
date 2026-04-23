"""
Organisation management — create, list, validate.
"""
import logging
import re
from functools import lru_cache

from app.cache import cache, keys, ttl
from app.repository.org_repository import OrgRepository

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r'^[a-z0-9_-]{2,64}$')


def _slugify(name: str) -> str:
    slug = re.sub(r'[^a-z0-9]+', '_', name.lower().strip()).strip('_')
    return slug[:64] or "org"


class OrgService:

    def __init__(self):
        self.repo = OrgRepository()

    def create(self, name: str, org_id: str = "") -> dict:
        """
        Create a new organisation.
        org_id is auto-derived from name if omitted.
        Raises ValueError on invalid slug or duplicate org_id.
        """
        if not name.strip():
            raise ValueError("name is required")

        org_id = org_id.strip() or _slugify(name)

        if not _SLUG_RE.match(org_id):
            raise ValueError(
                "org_id must be 2-64 chars, lowercase letters / digits / _ / -"
            )

        if self.repo.get_by_id(org_id):
            raise LookupError(f"org_id '{org_id}' already exists")

        org = self.repo.create(name=name.strip(), org_id=org_id)
        logger.info("Org created org_id=%s name=%s", org_id, name)
        return org

    async def list_all(self) -> list:
        return await cache.async_cache_or_fetch(
            keys.orgs_list(),
            ttl.ORG_LIST,
            lambda: self.repo.get_all(),
        )


@lru_cache()
def get_org_service() -> "OrgService":
    return OrgService()
