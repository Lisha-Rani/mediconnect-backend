import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.db.models import Appointment, Doctor, User
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/appointments", tags=["Doctor Appointments"])

# --- PYDANTIC REQUEST/RESPONSE SCHEMAS ---
class AppointmentCreate(BaseModel):
    doctor_id: int
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
    current_user: User = Depends(get_current_user)
):
    # 1. Verify that the requested doctor exists
    doc_query = await db.execute(select(Doctor).where(Doctor.id == payload.doctor_id))
    doctor = doc_query.scalars().first()
    if not doctor:
        raise HTTPException(status_code=404, detail="The requested medical practitioner does not exist.")

    # 2. Enforce validation (Handled safely in app memory to avoid PostgreSQL column mismatch errors)
    method = payload.payment_method.upper().strip()
    if method not in ["MOCK_ONLINE", "PAY_AT_CLINIC"]:
        raise HTTPException(status_code=400, detail="Invalid payment scheme. Choose MOCK_ONLINE or PAY_AT_CLINIC.")

    locked_fee = doctor.consultation_fee
    calculated_payment_status = "PENDING"
    
    if method == "MOCK_ONLINE":
        print(f"[MOCK PAYMENT SUCCESS] Processed automated checkout of ₹{locked_fee} for User ID {current_user.id}")
        calculated_payment_status = "COMPLETED"
    elif method == "PAY_AT_CLINIC":
        print(f"[COD BOOKING] Registered ₹{locked_fee} balance to be paid at the clinic facility.")
        calculated_payment_status = "PENDING"

    # 3. Parse date string safely into a native datetime object
    try:
        combined_datetime_str = f"{payload.appointment_date} {payload.appointment_time}"
        parsed_appointment_date = datetime.strptime(combined_datetime_str, "%Y-%m-%d %I:%M %p")
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail="Invalid date or time structure. Use YYYY-MM-DD and HH:MM AM/PM formats."
        )

    # 4. Save transaction using explicit baseline model layout parameters
    new_appointment = Appointment(
        patient_id=current_user.id,
        doctor_id=payload.doctor_id,
        appointment_date=parsed_appointment_date,
        status="SCHEDULED"
    )
    
    db.add(new_appointment)
    await db.commit()
    await db.refresh(new_appointment)
    
    # 5. Return complete schema block back to Next.js
    return AppointmentResponse(
        appointment_id=new_appointment.id,
        doctor_name=f"Dr. {doctor.first_name} {doctor.last_name}",
        specialization=doctor.specialization,
        appointment_date=payload.appointment_date,
        appointment_time=payload.appointment_time, 
        payment_method=method,                     
        amount=float(locked_fee),                  
        payment_status=calculated_payment_status,  
        booking_status=new_appointment.status
    )

# --- THE LISTING ENDPOINT ---
@router.get("/list", response_model=list)
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
        
        formatted.append({
            "time": appt.appointment_date.strftime("%I:%M %p") if appt.appointment_date else "10:00 AM",
            "name": p_name,
            "type": "Clinical Consultation",
            "status": appt.status.upper()
        })
    return formatted