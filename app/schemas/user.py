from pydantic import BaseModel, EmailStr
from app.db.models import RoleEnum
import uuid
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    role: RoleEnum = RoleEnum.PATIENT

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