from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.db.session import get_db
from app.db.models import User, Doctor, Appointment
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

    # 🌟 CRITICAL FIX: "id" must be the integer Doctor-table primary key
    # (current_user.doctor_id), NOT the User's UUID (current_user.id).
    # The frontend does Number(data.id) to get the doctor's bookable ID for
    # POST /appointments/book, which requires doctor_id: int. Returning the
    # UUID here made Number(uuid) => NaN, silently breaking every booking
    # attempt made from the doctor's "Fix Appointment" button.
    return {
        "id": current_user.doctor_id,
        "user_id": current_user.id,
        "first_name": current_user.first_name or "Attending",
        "last_name": current_user.last_name or "Physician",
        "specialization": specialization,
        "hospital_clinic": hospital_clinic,
        "city": city,
        "email": current_user.email,
        "consultation_fee": consultation_fee
    }


# 🌟 FIXED: Was returning every appointment (scheduled AND consulted) for
# this doctor, including — if the doctor's own account was ever used to book
# or run a symptom check while their own JWT was active (e.g. via the
# Patient/Provider preview toggle on the frontend, which only changes what
# the UI *shows* and does not switch accounts) — the doctor's own account
# appearing as a "patient". Now: only genuinely completed ("consulted")
# visits count as "treated patients", and the doctor's own user id is
# explicitly excluded as a defensive guard regardless of how bad data got in.
@router.get("/doctor/patients")
async def get_treated_patients(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role.lower() != "doctor":
        raise HTTPException(status_code=403, detail="Access denied. Account is not assigned a provider role.")

    if not current_user.doctor_id:
        return []

    result = await db.execute(
        select(Appointment).where(
            Appointment.doctor_id == current_user.doctor_id,
            Appointment.status == "consulted",
            Appointment.patient_id != current_user.id
        )
    )
    appointments = result.scalars().all()

    seen_patient_ids = set()
    patients = []
    for appt in appointments:
        pid = str(appt.patient_id)
        if pid in seen_patient_ids:
            continue
        seen_patient_ids.add(pid)

        p_res = await db.execute(select(User).where(User.id == appt.patient_id))
        patient = p_res.scalars().first()
        name = f"{patient.first_name} {patient.last_name}" if patient else "Verified Case"

        patients.append({
            "id": pid,
            "name": name,
            "patient_name": name,
            "last_visit": appt.appointment_date.strftime("%Y-%m-%d") if appt.appointment_date else None,
            "primary_condition": "Clinical Case"
        })

    return patients