from app.mock.sample_mock_data import get_mock_sample_requests

TIER_MAP = {
    "Vitamin C Face Massage Serum": "TIER_2",
    "Brightening Exfoliating Pads": "TIER_2",
    "Peach Foot Mask": "TIER_3",
    "Turmeric Cleansing Pads": "TIER_3",
    "Dummy Shoe Product": "TIER_1",
    "Melt & Clean Cleansing Balm": "TIER_4",
    "Kojic Acid Bar Soap": "TIER_4",
    "Hydrating Hand Mask": "TIER_1",
}


def fetch_sample_by_id(sample_id: str):
    responses = get_mock_sample_requests()

    applications = []
    for item in responses:
        applications.extend(item["data"]["sample_applications"])

    return next((a for a in applications if a["id"] == sample_id), None)


def get_tier(product_title: str) -> str:
    return TIER_MAP.get(product_title, "UNKNOWN")