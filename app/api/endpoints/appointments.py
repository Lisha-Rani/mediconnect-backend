import uuid
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
    appointment_id: str
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

    # 2. Enforce strict parameter validation on input methods
    method = payload.payment_method.upper().strip()
    if method not in ["MOCK_ONLINE", "PAY_AT_CLINIC"]:
        raise HTTPException(status_code=400, detail="Invalid payment scheme. Choose MOCK_ONLINE or PAY_AT_CLINIC.")

    calculated_payment_status = "PENDING"
    
    # 3. CRITICAL VALIDATION: Check that the exact amount matches the Doctor's specified Fee
    # 3. Automatically lock in the official fee from the database row
    locked_fee = doctor.consultation_fee
    calculated_payment_status = "PENDING"
    
    if method == "MOCK_ONLINE":
        print(f"[MOCK PAYMENT SUCCESS] Processed automated checkout of ₹{locked_fee} for User ID {current_user.id}")
        calculated_payment_status = "COMPLETED"
        
    elif method == "PAY_AT_CLINIC":
        print(f"[COD BOOKING] Registered ₹{locked_fee} balance to be paid at the clinic facility.")
        calculated_payment_status = "PENDING"
        
        
        
    

    # 4. Save the verified transaction
    new_appointment = Appointment(
        id=uuid.uuid4(),
        user_id=current_user.id,
        doctor_id=payload.doctor_id,
        appointment_date=payload.appointment_date,
        appointment_time=payload.appointment_time,
        status="SCHEDULED",
        payment_method=method,
        amount=locked_fee,  # Verified exact matching price
        payment_status=calculated_payment_status
    )
    
    db.add(new_appointment)
    await db.commit()

    return AppointmentResponse(
        appointment_id=str(new_appointment.id),
        doctor_name=f"Dr. {doctor.first_name} {doctor.last_name}",
        specialization=doctor.specialization,
        appointment_date=new_appointment.appointment_date,
        appointment_time=new_appointment.appointment_time,
        payment_method=new_appointment.payment_method,
        amount=new_appointment.amount,
        payment_status=new_appointment.payment_status,
        booking_status=new_appointment.status
    )