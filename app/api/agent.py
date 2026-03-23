from fastapi import APIRouter
from app.agents.sample_analyzer.runner import run_sr_agent

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post("/analyze/{sample_id}")
def analyze(sample_id: str):
    res = run_sr_agent(sample_id)
    return {
        "tier": res.get("tier"),
        "decision": res.get("final_decision"),
        "details": res.get("decision_reason") or res.get("llm_reasoning", "No details provided.")
    }