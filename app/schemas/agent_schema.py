from pydantic import BaseModel
from typing import List, Optional


class AgentAnalysisResponse(BaseModel):
    sample_id: str
    tier: str
    analysis_allowed: bool
    decision: Optional[str] = None
    reasoning: List[str] = []