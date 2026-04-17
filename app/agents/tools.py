import logging
from app.repository.tier_config_repository import TierConfigRepository

logger = logging.getLogger(__name__)


def fetch_sample_from_db(sample_id: str) -> dict | None:
    """Fetch the sample application document from sample_analyses Firestore collection."""
    from app.repository.sample_analysis_repository import SampleAnalysisRepository
    return SampleAnalysisRepository().get(sample_id)


def resolve_tier(org_id: str, username: str, product_id: str) -> tuple[str, dict]:
    """
    Determine the tier for a sample request using DB config (O(1) lookups).

    Priority:
      1. Is the creator on the Tier 1/2 list?  → TIER_1 or TIER_2, no thresholds
      2. Is the product in the Tier 3/4 config? → TIER_3 or TIER_4 + thresholds
      3. Neither                                → TIER_5, use global thresholds

    Returns (tier: str, thresholds: dict)
    """
    repo = TierConfigRepository()

    # 1. Creator list check — O(1) by composite doc ID
    creator_entry = repo.get_creator_tier(org_id, username)
    if creator_entry:
        logger.info("Creator '%s' matched %s list", username, creator_entry["tier"])
        return creator_entry["tier"], {}

    # 2. Product config check — O(1) by composite doc ID
    product_entry = repo.get_product_config(org_id, product_id)
    if product_entry:
        logger.info("Product '%s' matched %s config", product_id, product_entry["tier"])
        return product_entry["tier"], product_entry.get("thresholds") or {}

    # 3. Neither matched → Tier 5 with global thresholds
    tier5_thresholds = repo.get_tier5_thresholds(org_id)
    logger.info("No tier match for creator='%s' product='%s' → TIER_5", username, product_id)
    return "TIER_5", tier5_thresholds
