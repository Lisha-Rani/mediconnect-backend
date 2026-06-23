from pydantic import BaseModel, EmailStr
from app.db.models import RoleEnum
import uuid
from datetime import datetime

# What the Backend expects (Example):
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str | None = "Anonymous"
    last_name: str | None = "Patient"
    # 🔄 FIX: Make role optional with a clean default fallback string string
    role: str | None = "patient"

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