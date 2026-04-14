"""
Client-defined Visual Brand Safety Rubrics for Phase 4 video analysis.
Each product maps to specific video patterns and creator qualities the client
wants verified through direct video analysis.
"""

PRODUCT_RUBRICS: dict[str, dict] = {
    "Peach Foot Mask": {
        "patterns": [
            "Shows body care, not just face skincare",
            "Comfortable filming 'unpretty' or raw visuals",
            "Uses storytelling across multiple videos (updates, progress)",
            "Builds anticipation (teases results, 'wait for day 5')",
            "Has satisfying or curiosity-driven content",
            "Direct interaction with the audience",
            "Foot care, self-care reset, shower routine, vacation prep, sandal season, at-home pedicure content",
            "Has posted products where the transformation itself is the hook",
        ],
        "qualities": [
            "Doesn't over-polish content",
            "Good at reactions (their own or others')",
            "Strong retention in visual demo videos",
            "Comfortable filming close-up skin texture",
            "Good at follow-ups, not only single-post creators",
            "Body care content gets comments/questions",
        ],
    },
    "Turmeric Cleansing Pads": {
        "patterns": [
            "Routine-based content (AM/PM skincare)",
            "Shows step-by-step skincare application",
            "Close-up skin shots (texture, pores, dullness)",
            "Cleansing/exfoliation content already present",
            "Educational or 'this step matters' type of content",
            "Direct interaction with the audience (explaining benefits, answering questions)",
        ],
        "qualities": [
            "Clear, structured storytelling (not chaotic edits)",
            "Comfortable filming skin up close",
            "Audience asks skincare-related questions",
            "Consistent skincare niche (not random posting)",
        ],
    },
    "Marine Clay Mask": {
        "patterns": [
            "Talks about clogged pores, oily skin, breakouts, texture",
            "Shows real skin (visible pores, imperfections)",
            "Self-care / reset routines (weekly reset, skin detox)",
            "Close-up texture shots during and after use",
            "Educational or problem-solution skincare content",
            "Direct engagement with audience about skin concerns",
        ],
        "qualities": [
            "Trustworthy, non-hype tone",
            "Direct interaction with the audience (explaining benefits, answering questions)",
            "Comfortable showing imperfect skin",
            "Good at explaining skin concerns simply",
            "Content sparks discussion around skin issues",
        ],
    },
    "V-Line Lifting Mask": {
        "patterns": [
            "Face-focused content (angles, jawline, side profile)",
            "GRWM, event prep, glow-up, get ready with me content",
            "Beauty hacks or quick-result content",
            "Talks about puffiness, sculpting, contouring",
            "Before/after or transformation-style framing",
            "Close-up facial application content",
        ],
        "qualities": [
            "Confident showing face from multiple angles",
            "Direct interaction with the audience (explaining benefits, answering questions)",
            "Strong visual storytelling (clear difference or effect)",
            "Good at quick hooks and payoff",
            "Audience engages with appearance-based content",
        ],
    },
    "Jade Gua Sha": {
        "patterns": [
            "Morning/night routines (consistent habits)",
            "Step-by-step tutorials or how-to content",
            "Facial massage, depuffing, lymphatic drainage content",
            "Self-care, wellness, stress-relief angles",
            "Direct explanation of technique or benefits",
            "Minimal, clean visuals focused on the action",
        ],
        "qualities": [
            "Clear teaching ability",
            "Direct interaction with the audience (explaining benefits, answering questions)",
            "Relaxing, controlled delivery",
            "Feels credible in routine-based beauty",
        ],
    },
    "Kojic Acid Bar Soap": {
        "patterns": [
            "Talks about dark spots, uneven tone, texture, marks",
            "Body care content (not just face)",
            "Educational skincare content",
            "Consistent use narratives (not one-time use)",
            "Problem-solution framing (specific skin concern → solution)",
            "Close-up skin texture before/after (subtle, realistic)",
            "Direct interaction explaining use cases",
        ],
        "qualities": [
            "Direct interaction with the audience (explaining benefits, answering questions)",
            "Trustworthy and informative tone",
            "Comfortable discussing sensitive skin concerns",
            "Audience engages with problem-solving content",
            "Feels credible in both face + body care",
        ],
    },
    "Melt & Clean Cleansing Balm": {
        "patterns": [
            "Shows makeup removal or double-cleanse routines",
            "Demonstrates melting/texture of balm on skin",
            "Evening skincare routine content",
            "Educational cleansing content",
            "Close-up application shots",
            "Direct interaction explaining cleansing technique",
        ],
        "qualities": [
            "Comfortable with close-up skin and product shots",
            "Informative, step-by-step delivery",
            "Audience engages with skincare routine questions",
            "Consistent skincare or beauty niche",
        ],
    },
}


def get_product_rubric(product_title: str) -> dict | None:
    """Fuzzy lookup: return the rubric for a given product title."""
    if product_title in PRODUCT_RUBRICS:
        return PRODUCT_RUBRICS[product_title]
    # Partial match fallback (case-insensitive)
    lower = product_title.lower()
    for key, rubric in PRODUCT_RUBRICS.items():
        if key.lower() in lower or lower in key.lower():
            return rubric
    return None


def format_rubric_for_prompt(product_title: str) -> str:
    """Return a cleanly formatted rubric string ready to inject into an LLM prompt."""
    rubric = get_product_rubric(product_title)
    if not rubric:
        return "No specific client rubric defined for this product. Evaluate general skincare content quality."

    patterns = "\n".join(f"  - {p}" for p in rubric["patterns"])
    qualities = "\n".join(f"  - {q}" for q in rubric["qualities"])

    return f"""CLIENT-DEFINED VIDEO PATTERNS TO LOOK FOR:
{patterns}

CLIENT-DEFINED CREATOR QUALITIES TO VERIFY:
{qualities}"""
