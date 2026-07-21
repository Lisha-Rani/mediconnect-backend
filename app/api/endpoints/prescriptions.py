from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List

from app.db.models import User
from app.api.dependencies import get_current_user

router = APIRouter(tags=["Pharmacy Script Infrastructure"])

class PrescriptionCreate(BaseModel):
    patient_name: str
    medication_name: str
    dosage: str
    duration: str

# Temporary high-speed live memory array repository to handle script logging seamlessly
mock_prescription_database = [
    {
        "id": 1,
        "medication_name": "Paracetamol 650mg",
        "name": "Paracetamol 650mg",
        "patient_name": "Anonymous Case Archive",
        "patientName": "Anonymous Case Archive",
        "duration": "5 Days",
        "dosage": "1 tablet after meals",
        "prescriber": "MediAI Core Node"
    }
]

# 🌟 FIX: Both routes were completely unauthenticated — any unauthenticated
# request could read or write every patient's prescriptions. Added
# get_current_user like every other protected route in the app.
@router.get("/prescriptions", response_model=list)
async def get_all_active_prescriptions(
    current_user: User = Depends(get_current_user)
):
    return mock_prescription_database

@router.post("/prescriptions/create", status_code=status.HTTP_201_CREATED)
async def create_new_prescription(
    payload: PrescriptionCreate,
    current_user: User = Depends(get_current_user)
):
    if current_user.role.lower() != "doctor":
        raise HTTPException(status_code=403, detail="Only providers can issue prescriptions.")

    new_script = {
        "id": len(mock_prescription_database) + 1,
        "medication_name": payload.medication_name,
        "name": payload.medication_name,
        "patient_name": payload.patient_name,
        "patientName": payload.patient_name,
        "duration": payload.duration,
        "dosage": payload.dosage,
        "prescriber": f"Dr. {current_user.first_name or 'Attending'} {current_user.last_name or 'Staff'}".strip()
    }
    mock_prescription_database.append(new_script)
    return new_script
