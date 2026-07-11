from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.db.models import User, Doctor
from app.api.dependencies import get_current_user

router = APIRouter(tags=["Doctor Profile Infrastructure"])

@router.get("/doctor/profile")
async def get_doctor_profile(
    current_user: User = Depends(get_current_user), 
    db: AsyncSession = Depends(get_db)
):
    if current_user.role.lower() != "doctor":
        raise HTTPException(status_code=403, detail="Access denied. Account is not assigned a provider role.")
    
    specialization = "General Triage Review"
    hospital_clinic = "MediAI Central Clinic"
    city = "Patna"
    consultation_fee = 500

    try:
        result = await db.execute(select(Doctor).where(Doctor.email == current_user.email))
        doctor = result.scalars().first()
        if doctor:
            specialization = getattr(doctor, 'specialization', specialization)
            hospital_clinic = getattr(doctor, 'hospital_clinic', hospital_clinic)
            city = getattr(doctor, 'city', city)
            consultation_fee = getattr(doctor, 'consultation_fee', consultation_fee)
    except Exception:
        pass

    # 🌟 FIX: Explicitly map the string dictionary fields to prevent "Dr. undefined" in frontend layouts
    return {
        "id": current_user.id,
        "first_name": current_user.first_name or "Attending",
        "last_name": current_user.last_name or "Physician",
        "specialization": specialization,
        "hospital_clinic": hospital_clinic,
        "city": city,
        "email": current_user.email,
        "consultation_fee": consultation_fee
    }