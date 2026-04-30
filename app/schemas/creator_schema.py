"""
Creator metric descriptions schema.

Each field's `description` is the canonical, human-readable explanation
of that metric. The metadata endpoint exposes these to the frontend
so tooltip text is managed in one place.
"""
from pydantic import BaseModel, Field


class CreatorMetricDescriptions(BaseModel):
    followers: str = Field(
        description="Total TikTok followers."
    )
    est_gmv: str = Field(
        description="Gross Merchandise Value generated in the last 30 days."
    )
    units_sold: str = Field(
        description="Total product units sold via TikTok Shop affiliate links in the last 30 days."
    )
    products_promoted: str = Field(
        description="Number of distinct products promoted across TikTok Shop content."
    )
    avg_gmv_per_buyer: str = Field(
        description="Average revenue generated per unique buyer in the last 30 days."
    )
    gpm: str = Field(
        description="Gross Profit per Mille — average revenue earned per 1,000 video views in the last 30 days."
    )
    brand_collabs: str = Field(
        description="Number of brand collaborations completed on TikTok Shop."
    )
    post_rate: str = Field(
        description="Percentage of total posts that are EC (ecommerce) content."
    )
    video_engagement_rate: str = Field(
        description="Average (likes + comments + shares) ÷ views across EC videos in the last 30 days."
    )
    view_to_like_ratio: str = Field(
        description="Percentage of viewers who liked the video, averaged across EC videos in the last 30 days."
    )
    avg_views_per_video: str = Field(
        description="Average views per EC video in the last 30 days."
    )
    avg_likes_per_video: str = Field(
        description="Average likes per EC video in the last 30 days."
    )
    avg_comments_per_video: str = Field(
        description="Average comments per EC video in the last 30 days."
    )
    avg_shares_per_video: str = Field(
        description="Average shares per EC video in the last 30 days."
    )
