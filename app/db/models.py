import enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector # 🧠 🔄 Added for pgvector RAG support!
from app.db.session import Base

# 🔑 1. ROLE DEFINITION ENUM
import enum
# 🔄 Added Boolean to the SQLAlchemy imports list
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, UUID, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.db.session import Base

# 🔑 1. ROLE DEFINITION ENUM
class RoleEnum(str, enum.Enum):
    PATIENT = "patient"
    DOCTOR = "DOCTOR"


# 👤 2. USER ACCOUNT MODEL
class User(Base):
    __tablename__ = "users"

    id = Column(UUID, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default=RoleEnum.PATIENT.value)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=True)
    
    # 🔄 FIX: Added these two structural columns to satisfy your UserResponse validation schema!
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    doctor_profile = relationship("Doctor", back_populates="user_accounts")

# ... Leave all your other models (Doctor, Appointment, VisitRecord, etc.) exactly as they are below ...


# 🩺 3. MEDICAL PROVIDER PROFILE MODEL
class Doctor(Base):
    __tablename__ = "doctors"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    specialization = Column(String, nullable=False)
    hospital_clinic = Column(String, nullable=False)
    city = Column(String, nullable=False)
    consultation_fee = Column(Integer, default=450)

    # Relationships
    user_accounts = relationship("User", back_populates="doctor_profile")


# 📅 4. APPOINTMENT RESERVATIONS MODEL
class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    appointment_date = Column(DateTime, nullable=False)
    status = Column(String, default="scheduled")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# 🏥 5. CLINICAL VISITS RECORD MODEL
class VisitRecord(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(UUID, ForeignKey("users.id"), nullable=False)
    doctor_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    visit_date = Column(DateTime(timezone=True), server_default=func.now())
    diagnosis_notes = Column(Text, nullable=True)
    prescription = Column(Text, nullable=True)


# 📊 6. AI TRIAGE & DIAGNOSIS LOGS MODEL
class Diagnosis(Base):
    __tablename__ = "diagnoses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(UUID, ForeignKey("users.id"), nullable=True)
    transcript = Column(Text, nullable=False)
    ai_analysis = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# 🧠 7. KNOWLEDGE RETRIEVAL NODE MODEL (RAG Context)
class MedicalKnowledge(Base):
    __tablename__ = "medical_knowledge"

    id = Column(Integer, primary_key=True, index=True)
    disease_condition = Column(String, index=True, nullable=False)
    symptoms_summary = Column(Text, nullable=False)
    recommended_specialty = Column(String, nullable=False)
    
    # 🔄 FIX: Restored the embedding column for vector similarity search!
    # Note: 768 dimensions is standard for Gemini text-embedding-004. 
    # If your project uses OpenAI (text-embedding-ada-002), change this value to 1536!
    embedding = Column(Vector(384), nullable=True) 


# 💬 8. PERSISTENT CHAT MESSAGE MODEL
class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    room_id = Column(String, index=True, nullable=False)
    sender = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())