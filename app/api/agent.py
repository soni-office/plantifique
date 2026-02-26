from fastapi import APIRouter
from app.agents.sample_analysis_agent import SampleAnalysisAgent

router = APIRouter(prefix="/agent", tags=["Agent"])


@router.post("/analyze/{sample_id}")
def analyze(sample_id: str):
    return SampleAnalysisAgent.run(sample_id)