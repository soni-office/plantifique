from app.mock.sample_mock_data import get_mock_sample_requests

TIER_MAP = {
    "V-Line Sculpting Mask": "TIER_3",
    "Brightening Exfoliating Pads": "TIER_2",
    "Peach Foot Mask": "TIER_3",
    "Marine Clay Mask": "TIER_3",
    "Natural Jade Roller": "TIER_1",
    "Mango Cleansing Balm": "TIER_4",
    "Kojic Acid Bar Soap": "TIER_4",
}


def fetch_sample_by_id(sample_id: str):
    responses = get_mock_sample_requests()

    applications = []
    for item in responses:
        applications.extend(item["data"]["sample_applications"])

    return next((a for a in applications if a["id"] == sample_id), None)


def get_tier(product_title: str) -> str:
    return TIER_MAP.get(product_title, "UNKNOWN")