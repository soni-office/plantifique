"""
Metric description endpoint.

Descriptions live in:
  app/schemas/creator_schema.py  →  CreatorMetricDescriptions

FastAPI automatically exposes these Field descriptions in /docs.
The frontend fetches GET /tiktok/metadata/metric-descriptions once
on load and uses the descriptions to render metric tooltips.
"""
from fastapi import APIRouter

from app.schemas.creator_schema import CreatorMetricDescriptions

router = APIRouter(prefix="/tiktok/metadata", tags=["Metadata"])


@router.get("/metric-descriptions")
def get_metric_descriptions():
    """
    Returns human-readable descriptions for all creator metrics.
    The frontend fetches this once on load and uses the descriptions to render metric tooltips.
    """
    return {
        "creator": {
            field: info.description
            for field, info in CreatorMetricDescriptions.model_fields.items()
        },
    }
