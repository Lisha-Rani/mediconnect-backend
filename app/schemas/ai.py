from pydantic import BaseModel, EmailStr
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

class DoctorCreate(BaseModel):
    first_name: str
    last_name: str
    email: str                # 🔄 FIX: Make sure this is strictly required (no default = None)
    registration_number: str  # 🔄 FIX: Make sure this is strictly required (no default = None)
    specialization: str
    hospital_clinic: str
    city: str
    consultation_fee: int
    password:str

class DoctorResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    specialization: str
    hospital_clinic: str
    city: str
    consultation_fee: int
    class Config:
        from_attributes = True