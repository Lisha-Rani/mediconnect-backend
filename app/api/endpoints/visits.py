import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.db.models import Appointment, Doctor, User, VisitRecord
# Assuming you have a dependency to get the currently logged-in doctor
  

router = APIRouter(prefix="/visits", tags=["Post-Visit Management"])
# 🫱 Paste this temporary placeholder function:
async def get_current_doctor():
    class MockDoctor:
        id = 1  # This temporarily mocks Doctor ID 1 for testing
    return MockDoctor()
class CompleteVisitRequest(BaseModel):
    appointment_id: uuid.UUID
    doctor_advice: str
    diagnosis_notes: str | None = None

# --- SECURED COMPLETION ENDPOINT ---
@router.post("/complete")
async def complete_appointment(
    payload: CompleteVisitRequest, 
    db: AsyncSession = Depends(get_db),
    current_doctor: Doctor = Depends(get_current_doctor) # 👈 Enforces that a doctor must be logged in
):
    # 1. Fetch the appointment
    appt_query = await db.execute(select(Appointment).where(Appointment.id == payload.appointment_id))
    appointment = appt_query.scalars().first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment data not found.")

    # 2. SECURITY CHECK: Is this the doctor who was actually booked?
    if appointment.doctor_id != current_doctor.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Authorization failed. You cannot submit notes for an appointment assigned to another doctor."
        )

    # 3. Prevent duplicate notes if the visit was already completed
    existing_record = await db.execute(select(VisitRecord).where(VisitRecord.appointment_id == payload.appointment_id))
    if existing_record.scalars().first():
        raise HTTPException(status_code=400, detail="Medical advice has already been registered for this visit.")

    # 4. Update appointment status
    appointment.status = "COMPLETED"
    
    # 5. Save the digital prescription and advice notes
    record = VisitRecord(
        id=uuid.uuid4(),
        appointment_id=payload.appointment_id,
        doctor_advice=payload.doctor_advice,
        diagnosis_notes=payload.diagnosis_notes
    )
    db.add(record)
    await db.commit()
    
    return {"message": "Visit completed successfully. Notes securely published online."}


# --- DOWNLOADABLE RECEIPT ENDPOINT ---
@router.get("/download-receipt/{appointment_id}")
async def download_medical_receipt(appointment_id: str, db: AsyncSession = Depends(get_db)):
    appt_uuid = uuid.UUID(appointment_id)
    
    appt_data = await db.execute(select(Appointment).where(Appointment.id == appt_uuid))
    appt = appt_data.scalars().first()
    if not appt:
        raise HTTPException(status_code=404, detail="Appointment not found.")

    doc_data = await db.execute(select(Doctor).where(Doctor.id == appt.doctor_id))
    doc = doc_data.scalars().first()
    
    user_data = await db.execute(select(User).where(User.id == appt.user_id))
    user = user_data.scalars().first()

    rec_data = await db.execute(select(VisitRecord).where(VisitRecord.appointment_id == appt_uuid))
    record = rec_data.scalars().first()
    advice = record.doctor_advice if record else "No medical advice recorded yet."

    html_receipt = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; color: #333; }}
            .header {{ text-align: center; border-bottom: 2px solid #2A6F97; padding-bottom: 20px; }}
            .section {{ margin-top: 30px; }}
            .grid {{ display: flex; justify-content: space-between; margin-bottom: 15px; }}
            .box {{ border: 1px solid #ccc; padding: 15px; border-radius: 5px; background: #f9f9f9; min-height: 100px; }}
            .footer {{ margin-top: 60px; text-align: center; font-size: 12px; color: #777; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>MediAI Medical Summary & Receipt</h1>
            <p>Appointment ID: {appt.id}</p>
        </div>
        <div class="section">
            <div class="grid">
                <div><strong>Patient Name:</strong> {user.first_name if user else "Verified Profile"}</div>
                <div><strong>Date:</strong> {appt.appointment_date} | <strong>Time:</strong> {appt.appointment_time}</div>
            </div>
            <div style="margin-top: 10px;"><strong>Consulting Practitioner:</strong> Dr. {doc.first_name} {doc.last_name} ({doc.specialization})</div>
            <div><strong>Clinical Facility:</strong> {doc.hospital_clinic}, {doc.city}</div>
        </div>
        <hr/>
        <div class="section">
            <h3>🩺 Doctor's Medical Advice & Prescription</h3>
            <div class="box">{advice}</div>
        </div>
        <div class="section">
            <h3>💳 Payment Ledger</h3>
            <div class="grid">
                <div><strong>Method:</strong> {appt.payment_method}</div>
                <div><strong>Payment Status:</strong> {appt.payment_status}</div>
                <div><strong>Total Amount Settled:</strong> ₹{appt.amount}</div>
            </div>
        </div>
        <div class="footer">
            <p>Thank you for using MediAI Healthcare Services. This is an electronically generated document.</p>
        </div>
    </body>
    </html>
    """
    
    headers = {"Content-Disposition": f"attachment; filename=Receipt_{appointment_id}.html"}
    return Response(content=html_receipt, media_type="text/html", headers=headers)