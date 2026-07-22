import os
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.session import get_db
from app.db.models import Prescription, User, Doctor
from app.api.dependencies import get_current_user

router = APIRouter(tags=["Pharmacy Script Infrastructure"])

# 🌟 NOTE: Files are saved to local disk for now. For a real production
# deployment (multiple server instances, ephemeral filesystems on most
# hosting platforms) this should move to object storage (e.g. S3/R2) instead —
# flagging this here so it isn't forgotten, but local disk is a reasonable
# increment over "the file was never stored at all," which is where this
# started.
UPLOAD_DIR = "uploaded_files/prescriptions"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _serialize(rx: Prescription, patient_name: str = "") -> dict:
    return {
        "id": rx.id,
        "patient_id": str(rx.patient_id),
        "patient_name": patient_name,
        "patientName": patient_name,
        "doctor_id": rx.doctor_id,
        "medication_name": rx.medication_name,
        "name": rx.medication_name,
        "dosage": rx.dosage,
        "duration": rx.duration,
        "has_attachment": bool(rx.file_path),
        "file_name": rx.file_original_name,
        "created_at": rx.created_at.isoformat() if rx.created_at else None,
    }


# 🌟 REWRITTEN: previously an in-memory Python list with no real database
# table, no patient/doctor relationship, and matching done by comparing
# display-name strings on the frontend. Now backed by a real Prescription
# table, scoped per-user just like /appointments/list.
@router.get("/prescriptions")
async def get_my_prescriptions(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role.lower() == "doctor":
        if not current_user.doctor_id:
            return []
        result = await db.execute(
            select(Prescription).where(Prescription.doctor_id == current_user.doctor_id).order_by(Prescription.created_at.desc())
        )
        prescriptions = result.scalars().all()

        formatted = []
        for rx in prescriptions:
            p_res = await db.execute(select(User).where(User.id == rx.patient_id))
            patient = p_res.scalars().first()
            p_name = f"{patient.first_name} {patient.last_name}" if patient else "Verified Case"
            formatted.append(_serialize(rx, p_name))
        return formatted

    else:
        result = await db.execute(
            select(Prescription).where(Prescription.patient_id == current_user.id).order_by(Prescription.created_at.desc())
        )
        prescriptions = result.scalars().all()

        formatted = []
        for rx in prescriptions:
            d_res = await db.execute(select(Doctor).where(Doctor.id == rx.doctor_id))
            doctor = d_res.scalars().first()
            d_name = f"Dr. {doctor.first_name} {doctor.last_name}" if doctor else "Attending Physician"
            record = _serialize(rx)
            record["prescriber"] = d_name
            formatted.append(record)
        return formatted


# 🌟 REWRITTEN: now accepts multipart/form-data so an actual file can be
# attached — the old JSON-only endpoint had no way to receive a file at all,
# which is why the doctor's file picker never actually delivered anything.
@router.post("/prescriptions/create", status_code=status.HTTP_201_CREATED)
async def create_new_prescription(
    patient_id: str = Form(...),
    medication_name: str = Form(...),
    dosage: str = Form(...),
    duration: str = Form(...),
    file: UploadFile | None = File(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.role.lower() != "doctor" or not current_user.doctor_id:
        raise HTTPException(status_code=403, detail="Only providers can issue prescriptions.")

    try:
        target_patient_uuid = uuid.UUID(patient_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Provided patient identifier is not a valid UUID string.")

    stored_path = None
    original_name = None
    if file is not None and file.filename:
        original_name = file.filename
        ext = os.path.splitext(original_name)[1]
        stored_filename = f"{uuid.uuid4()}{ext}"
        stored_path = os.path.join(UPLOAD_DIR, stored_filename)
        contents = await file.read()
        with open(stored_path, "wb") as f:
            f.write(contents)

    new_rx = Prescription(
        patient_id=target_patient_uuid,
        doctor_id=current_user.doctor_id,
        medication_name=medication_name,
        dosage=dosage,
        duration=duration,
        file_path=stored_path,
        file_original_name=original_name,
    )
    db.add(new_rx)
    await db.commit()
    await db.refresh(new_rx)

    p_res = await db.execute(select(User).where(User.id == target_patient_uuid))
    patient = p_res.scalars().first()
    p_name = f"{patient.first_name} {patient.last_name}" if patient else "Verified Case"

    return _serialize(new_rx, p_name)


# 🌟 NEW: Lets either the prescribing doctor or the owning patient securely
# download the attached file. Nobody else can — the id alone isn't enough,
# the requester's account must actually match one side of the prescription.
@router.get("/prescriptions/download/{prescription_id}")
async def download_prescription_file(
    prescription_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Prescription).where(Prescription.id == prescription_id))
    rx = result.scalars().first()
    if not rx:
        raise HTTPException(status_code=404, detail="Prescription not found.")

    is_owning_patient = current_user.role.lower() == "patient" and rx.patient_id == current_user.id
    is_issuing_doctor = current_user.role.lower() == "doctor" and current_user.doctor_id == rx.doctor_id
    if not (is_owning_patient or is_issuing_doctor):
        raise HTTPException(status_code=403, detail="You do not have access to this prescription's attachment.")

    if not rx.file_path or not os.path.exists(rx.file_path):
        raise HTTPException(status_code=404, detail="No file attachment was uploaded for this prescription.")

    return FileResponse(
        path=rx.file_path,
        filename=rx.file_original_name or f"prescription_{rx.id}",
        media_type="application/octet-stream"
    )