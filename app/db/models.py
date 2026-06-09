import uuid
import enum
from datetime import datetime

# Consolidated all imports into clean, single lines
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON, Enum, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector

Base = declarative_base()

class RoleEnum(str, enum.Enum):
    PATIENT = "PATIENT"
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.PATIENT, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Link to primary doctor
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True)

class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    
    # FIX 1: Changed from Integer to UUID to match the User table perfectly!
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False) 
    
    transcript = Column(String)
    ai_analysis = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Link back to user
    user = relationship("User", backref="diagnoses")
    
    # Link to reviewing doctor
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True)
    
    # Doctor workflow columns (FIX 2: Text is now properly imported)
    diagnosis_title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    prescription_notes = Column(Text, nullable=True)

class MedicalKnowledge(Base):
    __tablename__ = "medical_knowledge"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    content = Column(String) 
    embedding = Column(Vector(384)) 
    source = Column(String) 

class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    registration_number = Column(String(100), unique=True, nullable=False) 
    specialization = Column(String(100), nullable=False)
    hospital_clinic = Column(String(200), nullable=False)
    city = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False) 
    consultation_fee = Column(Integer, default=500, nullable=False)  # 👈 Added here
    created_at = Column(DateTime(timezone=True), server_default=func.now())
class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    appointment_date = Column(String(50), nullable=False)
    appointment_time = Column(String(50), nullable=False)
    status = Column(String(50), default="SCHEDULED", nullable=False)  # SCHEDULED, CANCELLED
    payment_method = Column(String(50), nullable=False)  # MOCK_ONLINE, PAY_AT_CLINIC
    amount = Column(Integer, default=0)
    payment_status = Column(String(50), default="PENDING", nullable=False)  # PENDING, COMPLETED
    created_at = Column(DateTime, default=datetime.utcnow)