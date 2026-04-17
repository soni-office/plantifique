from app.agents.sample_analyzer.graph import build_graph
from app.agents.sample_analyzer.state import SREvaluationState

_graph = build_graph()


def run_sr_agent(
    sample_request_id: str,
    access_token: str = None,
    shop_cipher: str = None,
    threshold: int = 70,
) -> dict:
    initial_state: SREvaluationState = {
        "sample_request_id": sample_request_id,
        "access_token": access_token,
        "shop_cipher": shop_cipher,
        "threshold": threshold,
        "org_id": None,
        "tier": None,
        "creator_data": None,
        "rich_creator_data": None,
        "product_data": None,
        "product_title": None,
        "product_description": None,
        "thresholds": None,
        "post_rate": None,
        "filters_passed": None,
        "validation_reason": None,
        "recent_videos": None,
        "commerce_score": None,
        "commerce_reasoning": None,
        "aesthetic_score": None,
        "aesthetic_reasoning": None,
        "top_3_video_urls": None,
        "compatibility_status": None,
        "rich_creator_detail": None,
        "rich_product_detail": None,
        "final_decision": None,
        "decision_reason": None,
    }
    result = _graph.invoke(initial_state)

    # The detailed combined reasoning is generated inside decision_node
    combined_reasoning = result.get("decision_reason")

    return {
        "sample_request_id": sample_request_id,
        "tier": result.get("tier"),
        "filters_passed": result.get("filters_passed"),
        "validation_reason": result.get("validation_reason"),
        "commerce_score": result.get("commerce_score"),
        "commerce_reasoning": result.get("commerce_reasoning"),
        "aesthetic_score": result.get("aesthetic_score"),
        "aesthetic_reasoning": result.get("aesthetic_reasoning"),
        "top_3_video_urls": result.get("top_3_video_urls") or [],
        "visual_score": result.get("visual_score"),
        "visual_reasoning": result.get("visual_reasoning"),
        "compatibility_status": result.get("compatibility_status"),
        "rich_creator_detail": result.get("rich_creator_detail"),
        "rich_product_detail": result.get("rich_product_detail"),
        "final_decision": result.get("final_decision"),
        "decision_reason": combined_reasoning,
    }
