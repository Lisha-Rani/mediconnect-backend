import uuid  # 🔄 Added to generate clean UUID strings for user accounts
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.security import OAuth2PasswordRequestForm

from app.db.session import get_db
from app.db.models import User, Doctor, RoleEnum
from app.schemas.user import UserCreate, UserResponse, Token
from app.core.security import get_password_hash, verify_password, create_access_token
from app.schemas.ai import DoctorCreate, DoctorResponse

router = APIRouter()

# 👤 1. STANDARD PATIENT REGISTRATION
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    existing_user = result.scalars().first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered")
        
    # Hash password and save new user with an explicit UUID string string
    hashed_password = get_password_hash(user_data.password)
    new_user = User(
        id=str(uuid.uuid4()),  # 🔄 FIX: Explicitly provision a UUID to match the database configuration
        email=user_data.email,
        hashed_password=hashed_password,
        role=user_data.role
    )
    
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    return new_user


# 🔑 2. SECURE USER LOGIN GATEWAY
@router.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    # Find user by email (OAuth2 uses 'username' field for the email payload context)
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalars().first()
    
    # Verify user exists and credentials match
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # 🔄 FIX: Generate the JWT Token safely without trying to call .value on a plain string column!
    access_token = create_access_token(
        data={
            "sub": str(user.id), 
            "role": str(user.role)  # Reads the string column value directly out of the user object
        }
    )
    
    return {"access_token": access_token, "token_type": "bearer"}


# 🩺 3. SPECIALIZED MEDICAL PROVIDER REGISTRATION
@router.post("/register/doctor", response_model=DoctorResponse, status_code=status.HTTP_201_CREATED)
async def register_doctor(doctor_data: DoctorCreate, db: AsyncSession = Depends(get_db)):
    
    # Check if the email already exists in the User table
    user_check = await db.execute(select(User).where(User.email == doctor_data.email))
    if user_check.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered to a user account.")
        
    # Check if registration number already exists in Doctor table
    doc_check = await db.execute(select(Doctor).where(Doctor.registration_number == doctor_data.registration_number))
    if doc_check.scalars().first():
        raise HTTPException(status_code=400, detail="Medical registration number already exists.")

    # Hash the password
    hashed_password = get_password_hash(doctor_data.password)

    # Create the Doctor Profile record first
    new_doctor_profile = Doctor(
        first_name=doctor_data.first_name,
        last_name=doctor_data.last_name,
        specialization=doctor_data.specialization,
        hospital_clinic=doctor_data.hospital_clinic,
        city=doctor_data.city,
        consultation_fee=doctor_data.consultation_fee,
    )
    db.add(new_doctor_profile)
    await db.flush()  # Pushes profile to DB to generate the integer new_doctor_profile.id

    # Create the User login account and link it to the Doctor profile
    new_user = User(
        id=str(uuid.uuid4()),  # 🔄 FIX: Explicitly provision a UUID string here as well!
        email=doctor_data.email,
        hashed_password=hashed_password,
        role=RoleEnum.DOCTOR.value,  # 🔄 FIX: Converted enum instance to plain string for database write safety
        doctor_id=new_doctor_profile.id  # Links the account to the profile
    )
    db.add(new_user)
    
    # Safely commit both items at once
    await db.commit()
    await db.refresh(new_doctor_profile)
    
    return new_doctor_profile