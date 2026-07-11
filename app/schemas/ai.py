from pydantic import BaseModel, Field

class DoctorCreate(BaseModel):
    first_name: str = Field(..., description="Doctor's first name")
    last_name: str = Field(..., description="Doctor's last name")
    email: str = Field(..., description="Doctor's professional email address")
    password: str = Field(..., min_length=6, description="Account password")
    registration_number: str = Field(..., description="Medical registration/license number")
    specialization: str = Field(..., description="Medical specialty (e.g., Cardiologist, Dermatologist)")
    hospital_clinic: str = Field(..., description="Associated hospital or clinic name")
    city: str = Field(..., description="Operating city location")
    consultation_fee: int = Field(..., description="Consultation fee amount in INR")

class DoctorResponse(BaseModel):
    id: int
    first_name: str
    last_name: str
    email: str
    registration_number: str
    specialization: str
    hospital_clinic: str
    city: str
    consultation_fee: int

    class Config:
        from_attributes = True  # Allows SQLAlchemy ORM models to be parsed automatically