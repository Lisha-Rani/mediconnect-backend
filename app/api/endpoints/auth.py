import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from jose import jwt, JWTError

from app.db.session import get_db
from app.db.models import User, Doctor, RoleEnum
# 🌟 FIX: Use the shared security utilities (which read settings.SECRET_KEY
# from your .env) instead of the local hardcoded copies that used to live in
# this file. The old hardcoded SECRET_KEY here did not match settings.SECRET_KEY,
# which is what ai_chat.py (and get_current_user, presumably) verify tokens
# against — so every login-issued token silently failed auth anywhere else
# in the app, including the WebSocket chat.
from app.core.security import get_password_hash as hash_password, verify_password, create_access_token

router = APIRouter(prefix="/auth", tags=["System Authentication"])


# --- PYDANTIC VALIDATION SCHEMAS ---
class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str | None = "Anonymous"
    last_name: str | None = "Patient"
    role: str = "patient"  # 'patient' or 'doctor'
    
    # Optional fields required if registering a provider profile
    registration_number: str | None = None
    specialization: str | None = None
    hospital_clinic: str | None = None
    city: str | None = None
    consultation_fee: int | None = 450

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    role: str
    name: str


# =========================================================
# 📝 ROUTE 1: THE REGISTRATION CONTROLLER
# =========================================================
# 🌟 FIX: This single endpoint handles BOTH patient and doctor registration
# via the `role` field. The frontend previously posted to a separate
# /auth/register/doctor URL that never existed on the backend AND never
# sent `role` in the payload — see the accompanying register/page.tsx fix,
# which now posts here with role included.
@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_new_user(payload: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    # 1. Check if email handle is already registered
    existing_user_query = await db.execute(select(User).where(User.email == payload.email))
    if existing_user_query.scalars().first():
        raise HTTPException(status_code=400, detail="An account with this email address already exists.")

    # 2. Derive standardized lowercase role flags
    requested_role = payload.role.lower().strip()
    db_role_string = RoleEnum.PATIENT.value
    assigned_doctor_profile_id = None

    # 3. Handle specific provider profile requirements
    if requested_role == "doctor":
        # Force validation parameters for medical providers
        if not payload.registration_number or not payload.specialization or not payload.hospital_clinic:
            raise HTTPException(
                status_code=400, 
                detail="Medical registration number, specialization, and clinic details are required for doctors."
            )
            
        # Standardize matching to the uppercase Enum layout defined inside models.py
        db_role_string = "DOCTOR" 
        
        # Instantiate rows inside the doctors table
        new_doctor_profile = Doctor(
            first_name=payload.first_name or "Attending",
            last_name=payload.last_name or "Physician",
            email=payload.email,
            registration_number=payload.registration_number,
            specialization=payload.specialization,
            hospital_clinic=payload.hospital_clinic,
            city=payload.city or "Patna",
            consultation_fee=payload.consultation_fee or 500
        )
        db.add(new_doctor_profile)
        await db.flush()  # Populates new_doctor_profile.id instantly
        assigned_doctor_profile_id = new_doctor_profile.id

    # 4. Manually instantiate a clean native Python UUID object to satisfy column constraints
    fresh_user_uuid = uuid.uuid4()
    encrypted_pass = hash_password(payload.password)

    # 5. Build the unified core user authentication row
    new_user_account = User(
        id=fresh_user_uuid, # Passes a native structural UUID object securely
        email=payload.email,
        hashed_password=encrypted_pass,
        role=db_role_string,
        doctor_id=assigned_doctor_profile_id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        is_active=True
    )
    
    db.add(new_user_account)
    await db.commit()
    
    return {
        "status": "success",
        "message": f"Account successfully registered as {db_role_string.lower()}.",
        "user_id": str(fresh_user_uuid)
    }


# =========================================================
# 🔑 ROUTE 2: THE UNIFIED LOGIN CONTROLLER
# =========================================================
@router.post("/login", response_model=TokenResponse)
async def login_user(request: Request, db: AsyncSession = Depends(get_db)):
    # 1. Parse incoming payload safely regardless of frontend framework conventions
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON request payload structure.")

    # Extract identifier whether frontend sends it as 'email' or 'username'
    input_email = body.get("email") or body.get("username")
    input_password = body.get("password")

    if not input_email or not input_password:
        raise HTTPException(status_code=422, detail="Missing required authentication credentials fields.")

    # 2. Query database using normalized lowercase email strings
    clean_email = str(input_email).strip().lower()
    user_query = await db.execute(select(User).where(User.email == clean_email))
    user = user_query.scalars().first()
    
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials. Check email or password typing.")

    # 3. Validate password cryptography match against the User table baseline
    if not verify_password(input_password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials. Check email or password typing.")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="This account profile has been deactivated.")

    # 4. Standardize role strings and display formatting parameters
    user_display_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    user_role_str = "doctor" if str(user.role).upper() == "DOCTOR" else "patient"
    
    if user_role_str == "doctor":
        user_display_name = f"Dr. {user_display_name}".strip()

    # 5. Build secure token response model array
    token_claims = {
        "sub": str(user.id),  
        "email": user.email,
        "role": user_role_str,
        "id": str(user.id)
    }
    
    generated_jwt_token = create_access_token(data=token_claims)

    return TokenResponse(
        access_token=generated_jwt_token,
        token_type="bearer",
        role=user_role_str,
        name=user_display_name or "Verified User Node"
    )