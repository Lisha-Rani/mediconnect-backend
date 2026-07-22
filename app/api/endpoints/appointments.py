import uuid # 🌟 REQUIRED: Import Python's native UUID parsing library
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.db.models import Appointment, Doctor, User, Diagnosis
from app.api.dependencies import get_current_user

router = APIRouter(prefix="/appointments", tags=["Doctor Appointments"])

class AppointmentCreate(BaseModel):
    doctor_id: int
    patient_id: str 
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

@router.post("/book", response_model=AppointmentResponse, status_code=status.HTTP_201_CREATED)
async def book_doctor_appointment(
    payload: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    doc_query = await db.execute(select(Doctor).where(Doctor.id == payload.doctor_id))
    doctor = doc_query.scalars().first()
    if not doctor:
        raise HTTPException(status_code=404, detail="The requested medical practitioner does not exist.")

    try:
        combined_datetime_str = f"{payload.appointment_date} {payload.appointment_time}"
        parsed_appointment_date = datetime.strptime(combined_datetime_str, "%Y-%m-%d %I:%M %p")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time structure.")

    try:
        target_patient_uuid = uuid.UUID(payload.patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Provided patient identifier is not a valid UUID string.")

    new_appointment = Appointment(
        patient_id=target_patient_uuid,
        doctor_id=payload.doctor_id,
        appointment_date=parsed_appointment_date,
        status="scheduled"
    )
    db.add(new_appointment)
    
    triage_query = await db.execute(select(Diagnosis).where(Diagnosis.user_id == target_patient_uuid))
    active_triage_records = triage_query.scalars().all()
    for record in active_triage_records:
        await db.delete(record) 

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


# 🌟 REWRITTEN: This used to return EVERY appointment in the entire system
# to whoever called it — any logged-in patient could see every other
# patient's name and appointment details, and it never included doctor
# identity at all, which is why the patient-side "Doctors" tab had nothing
# real to show. It now scopes results to the caller and shapes the
# response appropriately for each role.
@router.get("/list")
async def get_my_appointments(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role.lower() == "doctor":
        if not current_user.doctor_id:
            return []

        # 🌟 FIX: Same guard as /doctor/patients — appointments where the
        # doctor's own account ended up as the patient (e.g. from using the
        # frontend's Patient/Provider preview toggle while still authenticated
        # as the doctor) were cluttering this list too. Excluded here as well.
        query = select(Appointment).where(
            Appointment.doctor_id == current_user.doctor_id,
            Appointment.patient_id != current_user.id
        ).order_by(Appointment.appointment_date.asc())
        result = await db.execute(query)
        appointments_list = result.scalars().all()

        formatted = []
        for appt in appointments_list:
            p_res = await db.execute(select(User).where(User.id == appt.patient_id))
            patient = p_res.scalars().first()
            p_name = f"{patient.first_name} {patient.last_name}" if patient else "Verified Case"

            formatted.append({
                "id": appt.id,
                "name": p_name,
                "patient_name": p_name,
                "patientName": p_name,
                "patient_id": str(appt.patient_id),
                "date": appt.appointment_date.strftime("%Y-%m-%d") if appt.appointment_date else None,
                "appointment_date": appt.appointment_date.strftime("%Y-%m-%d") if appt.appointment_date else None,
                "time": appt.appointment_date.strftime("%I:%M %p") if appt.appointment_date else None,
                "appointment_time": appt.appointment_date.strftime("%I:%M %p") if appt.appointment_date else None,
                "type": "Clinical Consultation",
                "specialty": "Clinical Consultation",
                "status": appt.status.upper()
            })
        return formatted

    else:
        # Patient view: scoped to their own appointments, with doctor identity included
        query = select(Appointment).where(
            Appointment.patient_id == current_user.id
        ).order_by(Appointment.appointment_date.asc())
        result = await db.execute(query)
        appointments_list = result.scalars().all()

        formatted = []
        for appt in appointments_list:
            d_res = await db.execute(select(Doctor).where(Doctor.id == appt.doctor_id))
            doctor = d_res.scalars().first()
            d_name = f"Dr. {doctor.first_name} {doctor.last_name}" if doctor else "Attending Physician"
            specialization = doctor.specialization if doctor else "General Medicine"

            formatted.append({
                "id": appt.id,
                "doctor_id": appt.doctor_id,
                "doctor_name": d_name,
                "specialization": specialization,
                "specialty": specialization,
                "date": appt.appointment_date.strftime("%Y-%m-%d") if appt.appointment_date else None,
                "appointment_date": appt.appointment_date.strftime("%Y-%m-%d") if appt.appointment_date else None,
                "time": appt.appointment_date.strftime("%I:%M %p") if appt.appointment_date else None,
                "appointment_time": appt.appointment_date.strftime("%I:%M %p") if appt.appointment_date else None,
                "status": appt.status.upper()
            })
        return formatted


@router.post("/complete/{appointment_id}")
async def complete_appointment_quick(
    appointment_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Appointment).where(Appointment.id == appointment_id))
    appointment = result.scalars().first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found.")

    appointment.status = "consulted"
    await db.commit()

    return {"message": "Appointment marked as consulted.", "id": appointment_id, "status": appointment.status}