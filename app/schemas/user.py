from pydantic import BaseModel, EmailStr
from app.db.models import RoleEnum
import uuid
from datetime import datetime

# What the Backend expects (Example):
class UserCreate(BaseModel):
    email: str
    password: str
    role: str # 'patient' or 'DOCTOR'

class UserResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: RoleEnum
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str