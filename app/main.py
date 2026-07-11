from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 📁 Explicitly import all endpoint routers from your app matrix
from app.api.endpoints import auth, ai, appointments, prescriptions, doctor
from app.db.session import engine
from app.db.models import Base

app = FastAPI(
    title="MediAI Healthcare Platform API",
    description="Unified core backend engine handling authentication, AI triage, and schedules.",
    version="1.0.0"
)

# =========================================================
# 🔒 CORS SECURITY HEADERS MIDDLEWARE CONFIGURATION
# =========================================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# 🔄 ROUTER WIRE-UP REGISTRY LAYER (API VERSION 1)
# =========================================================

# Registers /api/v1/auth/register and /api/v1/auth/login
app.include_router(auth.router, prefix="/api/v1")

# Registers /api/v1/ai/check and /api/v1/ai/doctor/queue
app.include_router(ai.router, prefix="/api/v1")

# Registers /api/v1/appointments/book and /api/v1/appointments/list
app.include_router(appointments.router, prefix="/api/v1")

# 🌟 WIRE-UP FIX: Explicitly mount the prescriptions registry to handle /api/v1/prescriptions
app.include_router(prescriptions.router, prefix="/api/v1")

# 🌟 WIRE-UP FIX: Explicitly mount the doctor tracking registry to handle /api/v1/doctor/profile and /api/v1/doctor/patients
app.include_router(doctor.router, prefix="/api/v1")


@app.get("/")
def read_root_status():
    return {
        "status": "online",
        "service": "MediAI Healthcare Core Node",
        "environment": "development"
    }