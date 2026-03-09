
from app.services.tiktok.client import TikTokClient
from app.core.config import settings
from app.mock.sample_mock_data import get_mock_sample_requests


CREATOR_PATH = "/affiliate_seller/202406/marketplace_creators/search"

# Build rich mock creators from sample data once at module load
def _build_mock_creators() -> list:
    """
    Extract and enrich creator objects from mock sample requests.
    Fields are shaped to match the frontend's Creator interface exactly.
    """
    # Extra data not present in sample_mock_data — keyed by creator username
    _EXTRA = {
        "rosesoma": {
            "avg_ec_video_view_count": 1996,
            "video_gmv": {"amount": "142300.50", "currency": "USD"},
            "selection_region": "US",
            "top_follower_demographics": {
                "age_ranges": ["18-24", "25-34"],
                "major_gender": {"gender": "FEMALE", "percentage": 7823},
            },
        },
        "influencedqueens": {
            "avg_ec_video_view_count": 7714,
            "video_gmv": {"amount": "310500.00", "currency": "USD"},
            "selection_region": "US",
            "top_follower_demographics": {
                "age_ranges": ["25-34", "35-44"],
                "major_gender": {"gender": "FEMALE", "percentage": 6542},
            },
        },
        "lexirosenstein": {
            "avg_ec_video_view_count": 3313,
            "video_gmv": {"amount": "198720.80", "currency": "USD"},
            "selection_region": "US",
            "top_follower_demographics": {
                "age_ranges": ["18-24", "25-34"],
                "major_gender": {"gender": "FEMALE", "percentage": 7110},
            },
        },
        "loreidysguzman": {
            "avg_ec_video_view_count": 131,
            "video_gmv": {"amount": "0", "currency": "USD"},
            "selection_region": "US",
            "top_follower_demographics": {
                "age_ranges": ["18-24"],
                "major_gender": {"gender": "FEMALE", "percentage": 5500},
            },
        },
        "una_flor_cubana": {
            "avg_ec_video_view_count": 5645,
            "video_gmv": {"amount": "502100.70", "currency": "USD"},
            "selection_region": "US",
            "top_follower_demographics": {
                "age_ranges": ["25-34", "35-44"],
                "major_gender": {"gender": "FEMALE", "percentage": 6890},
            },
        },
        "allure_fashion": {
            "avg_ec_video_view_count": 9611,
            "video_gmv": {"amount": "389200.00", "currency": "USD"},
            "selection_region": "US",
            "top_follower_demographics": {
                "age_ranges": ["18-24", "25-34"],
                "major_gender": {"gender": "FEMALE", "percentage": 8100},
            },
        },
        "naturefit_cole": {
            "avg_ec_video_view_count": 8069,
            "video_gmv": {"amount": "271400.25", "currency": "USD"},
            "selection_region": "US",
            "top_follower_demographics": {
                "age_ranges": ["25-34", "35-44"],
                "major_gender": {"gender": "MALE", "percentage": 5800},
            },
        },
    }

    seen = set()
    creators = []

    for sample_batch in get_mock_sample_requests():
        for application in sample_batch.get("data", {}).get("sample_applications", []):
            c = application.get("creator", {})
            username = c.get("username", "")
            if not username or username in seen:
                continue
            seen.add(username)

            extra = _EXTRA.get(username, {})
            creators.append({
                "creator_open_id": c.get("creator_open_id", ""),
                "username": username,
                "nickname": c.get("nickname", username),
                "avatar": {"url": c.get("avatar_url", "")},
                "follower_count": c.get("follower_count", 0),
                "avg_ec_video_view_count": extra.get("avg_ec_video_view_count", c.get("ec_video_view", 0)),
                "gmv": c.get("gmv", {"amount": "0", "currency": "USD"}),
                "video_gmv": extra.get("video_gmv", {"amount": "0", "currency": "USD"}),
                "selection_region": extra.get("selection_region", "US"),
                "content_count": c.get("content_count", 0),
                "fulfillment_percentage": c.get("fulfillment_percentage", "0"),
                "top_follower_demographics": extra.get("top_follower_demographics"),
            })

    return creators


_MOCK_CREATORS = _build_mock_creators()


class TikTokCreatorService:

    @staticmethod
    def get_creator(access_token: str, shop_cipher: str, page_size: int, keyword: str | None = None):
        if settings.mock_tiktok:
            results = _MOCK_CREATORS

            # Filter by keyword if provided (matches username or nickname)
            if keyword:
                kw = keyword.lower()
                results = [
                    c for c in results
                    if kw in c.get("username", "").lower()
                    or kw in c.get("nickname", "").lower()
                ]

            return {
                "code": 0,
                "message": "Success",
                "data": {
                    "creators": results[:page_size],
                    "total_count": len(results),
                },
            }

        qs = {"page_size": page_size}
        body = {}
        if keyword:
            body["keyword"] = keyword

        print("inside service tiktok creator service")
        return TikTokClient.post(
            path=CREATOR_PATH,
            access_token=access_token,
            shop_cipher=shop_cipher,
            qs=qs,
            body=body,
        )