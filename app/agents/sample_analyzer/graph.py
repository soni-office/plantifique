from langgraph.graph import StateGraph, END
from app.agents.sample_analyzer.state import SREvaluationState
from app.agents.sample_analyzer.nodes import (
    fetch_data_node,
    validation_node,
    route_after_validation,
    fetch_aesthetic_data_node,
    flag_internal_node,
    roi_check_node,
    route_after_roi,
    commerce_evaluation_node,
    aesthetic_evaluation_node,
    visual_evaluation_node,
    decision_node,
)


def build_graph() -> StateGraph:
    graph = StateGraph(SREvaluationState)

    graph.add_node("fetch_data", fetch_data_node)
    graph.add_node("validation", validation_node)
    graph.add_node("flag_internal", flag_internal_node)
    graph.add_node("roi_check", roi_check_node)
    graph.add_node("commerce_evaluation", commerce_evaluation_node)
    graph.add_node("fetch_aesthetic_data", fetch_aesthetic_data_node)
    graph.add_node("aesthetic_evaluation", aesthetic_evaluation_node)
    graph.add_node("visual_evaluation", visual_evaluation_node)
    graph.add_node("decision", decision_node)

    graph.set_entry_point("fetch_data")
    graph.add_edge("fetch_data", "validation")

    graph.add_conditional_edges(
        "validation",
        route_after_validation,
        {
            "flag_internal": "flag_internal",
            "roi_check": "roi_check",
            "decision": "decision",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "roi_check",
        route_after_roi,
        {
            "decision": "decision",
            "commerce_evaluation": "commerce_evaluation",
        },
    )

    graph.add_edge("flag_internal", END)

    graph.add_edge("commerce_evaluation", "fetch_aesthetic_data")
    graph.add_edge("fetch_aesthetic_data", "aesthetic_evaluation")
    graph.add_edge("aesthetic_evaluation", "visual_evaluation")
    graph.add_edge("visual_evaluation", "decision")

    graph.add_edge("decision", END)

    return graph.compile()
