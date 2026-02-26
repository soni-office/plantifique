# from app.agents.tools import fetch_sample_by_id, get_tier
# from app.services.llm.llm_client import MinimaxClient


# # Tier 3 Rules
# TIER_3_RULES = {
#     "Peach Foot Mask": {"gmv": 800, "followers": 0},
#     "Marine Clay Mask": {"gmv": 1000, "followers": 5000},
#     "V-Line Sculpting Mask": {"gmv": 1000, "followers": 5000},
# }

# # Tier 4 Rules
# TIER_4_RULES = {
#     "Mango Cleansing Balm": {"gmv": 1000, "followers": 5000},
#     "Kojic Acid Bar Soap": {"gmv": 1000, "followers": 0},
# }


# class SampleAnalysisAgent:

#     @staticmethod
#     def run(sample_id: str):

#         sample = fetch_sample_by_id(sample_id)

#         if not sample:
#             return {
#                 "sample_id": sample_id,
#                 "tier": "UNKNOWN",
#                 "decision": "ERROR",
#                 "summary": "Sample not found",
#                 "details": "The requested sample ID could not be located."
#             }

#         creator = sample["creator"]
#         product = sample["product"]

#         follower_count = creator["follower_count"]
#         gmv = float(creator["gmv"]["amount"])
#         content_count = creator["content_count"]
#         product_title = product["title"]

#         tier = get_tier(product_title)

#         # 🔹 Tier 1 & 2
#         if tier in ["TIER_1", "TIER_2"]:
#             return {
#                 "sample_id": sample_id,
#                 "tier": tier,
#                 "decision": "INFO",
#                 "summary": f"{tier} strategic product",
#                 "details": "This is a strategic product and does not require analysis."
#             }

#         # 🔹 Tier 3 or 4 Rule Selection
#         rule_set = TIER_3_RULES if tier == "TIER_3" else TIER_4_RULES
#         rule = rule_set.get(product_title)

#         if not rule:
#             return {
#                 "sample_id": sample_id,
#                 "tier": tier,
#                 "decision": "UNKNOWN",
#                 "summary": "No rule defined",
#                 "details": "No approval rule is configured for this product."
#             }

#         required_gmv = rule["gmv"]
#         required_followers = rule["followers"]

#         decision = "APPROVE"
#         failed_conditions = []

#         if gmv < required_gmv:
#             decision = "REJECT"
#             failed_conditions.append("GMV below threshold")

#         if follower_count < required_followers:
#             decision = "REJECT"
#             failed_conditions.append("Followers below threshold")

#         # Tier 4 ROI Exception
#         if tier == "TIER_4" and decision == "APPROVE":
#             has_high_roi = gmv >= 500000
#             if not has_high_roi:
#                 decision = "REJECT"
#                 failed_conditions.append("No high historical ROI")

#         # 🔥 Send structured data to LLM
#         prompt = f"""
#         Product: {product_title}
#         Tier: {tier}

#         Required Thresholds:
#         - GMV >= {required_gmv}
#         - Followers >= {required_followers}

#         Creator Metrics:
#         - GMV: {gmv}
#         - Followers: {follower_count}
#         - Content Count: {content_count}

#         Final Decision: {decision}

#         Explain clearly:
#         1. Whether GMV exceeds threshold.
#         2. Whether followers exceed threshold.
#         3. Why the final decision is {decision}.
#         Keep it concise but include numeric comparisons.
#         """

#         llm = MinimaxClient()
#         explanation = llm.generate_analysis(prompt)

#         return {
#             "sample_id": sample_id,
#             "tier": tier,
#             "decision": decision,
#             "summary": f"{decision} — Tier {tier.split('_')[1]} evaluation",
#             "details": explanation
#         }



from app.agents.tools import fetch_sample_by_id, get_tier


# Tier 3 Rules
TIER_3_RULES = {
    "Peach Foot Mask": {"gmv": 800, "followers": 0},
    "Marine Clay Mask": {"gmv": 1000, "followers": 5000},
    "V-Line Sculpting Mask": {"gmv": 1000, "followers": 5000},
}

# Tier 4 Rules
TIER_4_RULES = {
    "Mango Cleansing Balm": {"gmv": 1000, "followers": 5000},
    "Kojic Acid Bar Soap": {"gmv": 1000, "followers": 0},
}


class SampleAnalysisAgent:

    @staticmethod
    def run(sample_id: str):

        sample = fetch_sample_by_id(sample_id)

        if not sample:
            return {
                "sample_id": sample_id,
                "tier": "UNKNOWN",
                "decision": "ERROR",
                "summary": "Sample not found",
                "details": "The requested sample ID could not be located."
            }

        creator = sample["creator"]
        product = sample["product"]

        follower_count = creator["follower_count"]
        gmv = float(creator["gmv"]["amount"])
        content_count = creator["content_count"]
        product_title = product["title"]

        tier = get_tier(product_title)

        # 🔹 Tier 1 & 2 (No Analysis)
        if tier in ["TIER_1", "TIER_2"]:
            return {
                "sample_id": sample_id,
                "tier": tier,
                "decision": "INFO",
                "summary": f"{tier} strategic product",
                "details": "This is a strategic product and does not require analysis."
            }

        # 🔹 Select Rule Set
        rule_set = TIER_3_RULES if tier == "TIER_3" else TIER_4_RULES
        rule = rule_set.get(product_title)

        if not rule:
            return {
                "sample_id": sample_id,
                "tier": tier,
                "decision": "UNKNOWN",
                "summary": "No rule configured",
                "details": "No approval rule exists for this product."
            }

        required_gmv = rule["gmv"]
        required_followers = rule["followers"]

        decision = "APPROVE"
        explanations = []

        # GMV check
        if gmv >= required_gmv:
            explanations.append(
                f"GMV (${gmv}) exceeds required threshold of ${required_gmv}."
            )
        else:
            explanations.append(
                f"GMV (${gmv}) is below required threshold of ${required_gmv}."
            )
            decision = "REJECT"

        # Follower check
        if follower_count >= required_followers:
            explanations.append(
                f"Follower count ({follower_count}) meets minimum requirement of {required_followers}."
            )
        else:
            explanations.append(
                f"Follower count ({follower_count}) is below required minimum of {required_followers}."
            )
            decision = "REJECT"

        # Tier 4 ROI exception simulation
        if tier == "TIER_4" and decision == "APPROVE":
            has_high_roi = gmv >= 500000

            if has_high_roi:
                explanations.append(
                    "High historical ROI condition satisfied for Tier 4 legacy product."
                )
            else:
                explanations.append(
                    "Does not meet high historical ROI condition required for Tier 4 approval."
                )
                decision = "REJECT"

        return {
            "sample_id": sample_id,
            "tier": tier,
            "decision": decision,
            "summary": f"{decision} — {tier} evaluation",
            "details": " ".join(explanations),
        }