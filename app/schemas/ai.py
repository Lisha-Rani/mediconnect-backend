from pydantic import BaseModel
from typing import Dict, Any, List

class SymptomAnalysisResponse(BaseModel):
    severity: str
    explanation: str
    precautions: List[str]
    recommend_doctor: bool
    disclaimer: str

class VoiceAnalysisResponse(BaseModel):
    success: bool
    transcript: str
    analysis: Dict[str, Any]