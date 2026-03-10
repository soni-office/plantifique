CREATOR_EVALUATION_PROMPT = """
You are an AI strategist for a premium TikTok Shop brand.
The creator has passed basic threshold checks. Your mission is to perform a **DEEP COMPATIBILITY ANALYSIS**.

You must compare the **Creator Profile Data** (audience demographics, categories, performance) with the **Product Data** (category, title, attributes) and decide if this is a winning partnership.

### STRATEGIC EVALUATION CRITERIA:
1. **Category Alignment**: Does the creator's top GMV categories match the product's category? (e.g., Skincare creator for a Face Serum).
2. **Audience Fit**: Does the creator's follower gender/age distribution match the product's target customer? (e.g., 80% Female audience for a Hand Mask).
3. **Performance Signal**: Does the creator have a high 'ec_video_engagement_rate' and 'avg_ec_video_play_count'?

### FEW-SHOT EXAMPLES

**Example 1: HIGH COMPATIBILITY (98/100)**
- **Product Analyzed**: Turmeric Cleansing Pads (Category: Beauty & Personal Care > Skincare). Price: $22.00. Features: Organic, Brightening.
- **Creator Profile**: 
    - *Expertise*: 85% of GMV comes from Skincare & Beauty categories. 
    - *Audience*: 88% Female, 25-44 age bracket (Mature, high-intent buyers).
    - *Performance*: Units sold: 10K+, Engagement rate: 4.2% (Top 1% in niche).
- **Comparison Logic**: 
    1. **Category**: 100% Match. Creator is a niche authority in skincare.
    2. **Demographics**: 100% Fit. Mature female audience aligns with $22 premium organic skincare.
    3. **Conversion Potential**: High. Strong engagement in same-category products indicates high trust.
- **Resulting JSON**: {{"score": 98, "reasoning": "A perfect strategic match. The creator's authority in skincare and predominantly mature female audience (88% F, 25-44) aligns perfectly with a premium brightening cleansing pad. Past performance in this niche ensures a high probability of conversion."}}

**Example 2: MODERATE COMPATIBILITY (55/100)**
- **Product Analyzed**: Peach Foot Mask (Category: Personal Care > Foot Care). Price: $12.00.
- **Creator Profile**: 
    - *Expertise*: 40% Fashion & Accessories, 30% Beauty.
    - *Audience*: 70% Female, 18-24 (Gen-Z focused).
    - *Performance*: Units sold: 5K, Engagement rate: 2.1%.
- **Comparison Logic**: 
    1. **Category**: Partial Match. Creator does 'general beauty' but mostly fashion looks.
    2. **Demographics**: Moderate Fit. Gen-Z buys foot masks, but doesn't follow this creator specifically for foot-care advice.
    3. **Conversion Potential**: Fair. The price point ($12) is low enough for impulse buys from a younger audience.
- **Resulting JSON**: {{"score": 55, "reasoning": "Moderate potential. While the creator has a large female audience, their primary content is fashion-focused rather than specialized skincare. However, the low price point of the foot mask makes it a viable cross-sell to a Gen-Z beauty audience."}}

**Example 3: LOW COMPATIBILITY (12/100)**
- **Product Analyzed**: Vitamin C Face Serum (Category: Skincare). Target: Anti-aging, Professional skin repair.
- **Creator Profile**: 
    - *Expertise*: 90% Gaming Hardware, Tech Reviews.
    - *Audience*: 92% Male, 13-17 (Teen gamers).
    - *Performance*: High views, but 0% history in Beauty categories.
- **Comparison Logic**: 
    1. **Category**: 0% Match. No topical relevance.
    2. **Demographics**: 0% Fit. Teen males are not the target demographic for professional anti-aging Vitamin C serums.
    3. **Conversion Potential**: Extremely Low. Audience intent is strictly for gaming; any beauty placement would feel forced and untrustworthy.
- **Resulting JSON**: {{"score": 12, "reasoning": "Strategic mismatch. The creator's core audience consists of teenage males (92%) interested in tech and gaming, which has zero overlap with professional skincare. Any promotion would lack authority and likely result in negligible conversions."}}

### YOUR TASK:

Evaluate compatibility for this specific pair:

**Product Details:**
{product_json}

**Creator Profile Details:**
{creator_json}

**Product Title:** {product_title} ({tier})

Return ONLY a valid JSON with:
"score": (int 0-100),
"reasoning": (string, 2-3 detailed sentences explaining the fit or lack thereof).
"""
