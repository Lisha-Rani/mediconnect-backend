from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import List

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

@router.get("/prescriptions", response_model=list)
async def get_all_active_prescriptions():
    return mock_prescription_database

@router.post("/prescriptions/create", status_code=status.HTTP_201_CREATED)
async def create_new_prescription(payload: PrescriptionCreate):
    new_script = {
        "id": len(mock_prescription_database) + 1,
        "medication_name": payload.medication_name,
        "name": payload.medication_name,
        "patient_name": payload.patient_name,
        "patientName": payload.patient_name,
        "duration": payload.duration,
        "dosage": payload.dosage,
        "prescriber": "Dr. Attending Staff Node"
    }
    mock_prescription_database.append(new_script)
    return new_script