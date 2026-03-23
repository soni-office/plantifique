from langgraph.graph import StateGraph, END
from app.agents.sample_analyzer.state import SREvaluationState
from app.agents.sample_analyzer.nodes import (
    fetch_data_node,
    validation_node,
    route_after_validation,
    flag_internal_node,
    llm_score_node,
    decision_node
)

def build_graph() -> StateGraph:

    graph = StateGraph(SREvaluationState)

    # 1. Register Nodes
    graph.add_node("fetch_data", fetch_data_node)
    graph.add_node("validation", validation_node)
    graph.add_node("flag_internal", flag_internal_node)
    graph.add_node("llm_score", llm_score_node)
    graph.add_node("decision", decision_node)

    # 2. Define Entry Point
    graph.set_entry_point("fetch_data")

    # 3. Add Edges/Routing Rules
    graph.add_edge("fetch_data", "validation")
    
    graph.add_conditional_edges(
        "validation",
        route_after_validation,
        {
            "flag_internal": "flag_internal",
            "llm_score": "llm_score",
            "decision": "decision",
            "end": END,
        },
    )

    # 4. Define Terminal Exits
    graph.add_edge("flag_internal", END)
    graph.add_edge("llm_score", "decision")
    graph.add_edge("decision", END)

    return graph.compile()
