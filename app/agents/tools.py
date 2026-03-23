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

# Tier 3 minimum thresholds
TIER_3_THRESHOLDS = {
    "Peach Foot Mask":         {"min_gmv": 800,  "min_followers": 0,    "min_post_rate": 65},
    "Turmeric Cleansing Pads": {"min_gmv": 1000, "min_followers": 5000, "min_post_rate": 75},
    "Marine Clay Mask":        {"min_gmv": 1000, "min_followers": 5000, "min_post_rate": 75},
    "V-Line Mask":             {"min_gmv": 1000, "min_followers": 5000, "min_post_rate": 65},
    "Jade Gua Sha":            {"min_gmv": 1000, "min_followers": 5000, "min_post_rate": 75},
}

# Tier 4 baseline thresholds
TIER_4_THRESHOLDS = {
    "Mango Cleansing Balm": {"min_gmv": 1000, "min_followers": 5000, "min_post_rate": 80},
    "Melt & Clean Cleansing Balm": {"min_gmv": 1000, "min_followers": 5000, "min_post_rate": 80},
    "Kojic Acid Bar Soap":  {"min_gmv": 1000, "min_followers": 0,    "min_post_rate": 65},
}

def fetch_sample_by_id(sample_id: str, access_token: str = None, shop_cipher: str = None):
    responses = get_mock_sample_requests()

    applications = []
    for item in responses:
        if item.get("data") and "sample_applications" in item["data"]:
            applications.extend(item["data"]["sample_applications"])

    return next((a for a in applications if a.get("id") == sample_id), None)


def get_tier(product_title: str) -> str:
    return TIER_MAP.get(product_title, "UNKNOWN")