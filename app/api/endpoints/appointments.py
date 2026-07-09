import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.db.models import Appointment, Doctor, User, Diagnosis
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/appointments", tags=["Doctor Appointments"])

# --- PYDANTIC REQUEST/RESPONSE SCHEMAS ---
class AppointmentCreate(BaseModel):
    doctor_id: int
    patient_id: str # 🌟 FIX: Changed from int to str to support true UUID string tokens safely!
    appointment_date: str = Field(description="Format: YYYY-MM-DD")
    appointment_time: str = Field(description="Format: 10:30 AM")
    payment_method: str = Field(description="Must be exactly: MOCK_ONLINE or PAY_AT_CLINIC")

class AppointmentResponse(BaseModel):
    appointment_id: int  
    doctor_name: str
    specialization: str
    appointment_date: str
    appointment_time: str
    payment_method: str
    amount: float
    payment_status: str
    booking_status: str

# --- THE BOOKING ENDPOINT ---
@router.post("/book", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def book_doctor_appointment(
    payload: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user) # Used to verify authorization context
):
    # 1. Verify that the requested doctor exists
    doc_query = await db.execute(select(Doctor).where(Doctor.id == payload.doctor_id))
    doctor = doc_query.scalars().first()
    if not doctor:
        raise HTTPException(status_code=404, detail="The requested medical practitioner does not exist.")

    # 2. Parse date string safely into a native datetime object
    try:
        combined_datetime_str = f"{payload.appointment_date} {payload.appointment_time}"
        parsed_appointment_date = datetime.strptime(combined_datetime_str, "%Y-%m-%d %I:%M %p")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time structure.")

    # 3. Save transaction using payload.patient_id as a persistent string UUID
    new_appointment = Appointment(
        patient_id=payload.patient_id, # 🌟 FIX: Links row to the true string UUID
        doctor_id=payload.doctor_id,
        appointment_date=parsed_appointment_date,
        status="SCHEDULED"
    )
    db.add(new_appointment)
    
    # 🌟 4. THE FIX: Target and wipe out the actual Patient's active triage queue records using the string token!
    triage_query = await db.execute(select(Diagnosis).where(Diagnosis.user_id == payload.patient_id))
    active_triage_records = triage_query.scalars().all()
    print(f"➔ [MediAI Debug] Attempting to clear queue for patient_id: {payload.patient_id}")
    print(f"➔ [MediAI Debug] Number of active triage records found to delete: {len(active_triage_records)}")
    for record in active_triage_records:
        await db.delete(record) 

    await db.commit()
    await db.refresh(new_appointment)
    
    # 5. Return complete schema block back to Next.js
    return AppointmentResponse(
        appointment_id=new_appointment.id,
        doctor_name=f"Dr. {doctor.first_name} {doctor.last_name}",
        specialization=doctor.specialization,
        appointment_date=payload.appointment_date,
        appointment_time=payload.appointment_time, 
        payment_method=payload.payment_method,                    
        amount=float(doctor.consultation_fee),                  
        payment_status="PENDING",  
        booking_status=new_appointment.status
    )

# --- THE LISTING ENDPOINT ---
@router.get("/list")
async def get_all_doctor_appointments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = select(Appointment).order_by(Appointment.appointment_date.asc())
    result = await db.execute(query)
    appointments_list = result.scalars().all()
    
    formatted = []
    for appt in appointments_list:
        p_res = await db.execute(select(User).where(User.id == appt.patient_id))
        patient = p_res.scalars().first()
        p_name = f"{patient.first_name} {patient.last_name}" if patient else "Verified Case"
        
        # 🔄 FIX: Send explicit date strings and layout-matching structural keys
        formatted.append({
            "id": appt.id,
            "name": p_name,
            "patient_name": p_name,
            "patientName": p_name,
            "patient_id": str(appt.patient_id),
            "date": appt.appointment_date.strftime("%Y-%m-%d") if appt.appointment_date else "2026-07-10",
            "appointment_date": appt.appointment_date.strftime("%Y-%m-%d") if appt.appointment_date else "2026-07-10",
            "time": appt.appointment_date.strftime("%I:%M %p") if appt.appointment_date else "10:00 AM",
            "appointment_time": appt.appointment_date.strftime("%I:%M %p") if appt.appointment_date else "10:00 AM",
            "type": "Clinical Consultation",
            "specialty": "Clinical Consultation",
            "status": appt.status.upper() # Keeps 'SCHEDULED' or 'CONSULTED' status constraints intact
        })
    return formatted