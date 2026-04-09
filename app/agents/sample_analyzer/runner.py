from app.agents.sample_analyzer.graph import build_graph
from app.agents.sample_analyzer.state import SREvaluationState

_graph = build_graph()


def run_sr_agent(sample_request_id: str, access_token: str = None, shop_cipher: str = None, threshold: int = 70) -> dict:
    
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
        "thresholds": None,
        "post_rate": None,
        "llm_score": None,
        "llm_reasoning": None,
        "final_decision": None,
        "decision_reason": None,
    }

    result = _graph.invoke(initial_state)

    return {
        "sample_request_id": sample_request_id,
        "tier": result.get("tier"),
        "filters_passed": result.get("filters_passed"),
        "validation_reason": result.get("validation_reason"),
        "llm_score": result.get("llm_score"),
        "llm_reasoning": result.get("llm_reasoning"),
        "compatibility_status": result.get("compatibility_status"),
        "rich_creator_detail": result.get("rich_creator_detail"),
        "rich_product_detail": result.get("rich_product_detail"),
        "final_decision": result.get("final_decision"),
        "decision_reason": result.get("decision_reason"),
    }
