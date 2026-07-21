from fastapi import APIRouter, Depends, HTTPException
from app.db.models import User
from app.api.dependencies import get_current_user

router = APIRouter(tags=["Patient Profile Infrastructure"])

# 🌟 NEW FILE: This endpoint was called by the frontend (fetchDatabaseProfile
# in page.tsx) but did not exist anywhere in the backend, so it always 404'd
# (and was additionally being masked to a fake [] by the FetchInterceptor script).
@router.get("/patient/profile")
async def get_patient_profile(
    current_user: User = Depends(get_current_user)
):
    if current_user.role.lower() != "patient":
        raise HTTPException(status_code=403, detail="Access denied. Account is not assigned a patient role.")

    return {
        "id": current_user.id,
        "first_name": current_user.first_name or "Anonymous",
        "last_name": current_user.last_name or "Patient",
        "email": current_user.email,
    }
