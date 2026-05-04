from pydantic import BaseModel
from typing import Optional

class FeedbackBody(BaseModel):
    rating: str
    comment: str = ""


class ReviewStatusBody(BaseModel):
    # Internal status saved in our Firestore DB (e.g. "APPROVED", "REJECTED")
    status: str
    # Maps directly to TikTok's review_result field: "APPROVE" or "REJECT"
    review_result: str
    # Required by TikTok when review_result is "REJECT".
    # One of: NOT_MATCH | OFFLINE | OUT_OF_STOCK | OTHER
    reject_reason: Optional[str] = None
