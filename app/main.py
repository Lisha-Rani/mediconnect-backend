from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 📁 Explicitly import all endpoint routers from your app matrix
# 🌟 FIX: Added ai_chat, visits, and patient — these existed on disk but were
#    never imported, so their routes silently never registered with FastAPI.
from app.api.endpoints import auth, ai, appointments, prescriptions, doctor, patient, ai_chat, visits
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

# Registers /api/v1/ai/check, /api/v1/ai/history, and /api/v1/ai/doctor/queue
app.include_router(ai.router, prefix="/api/v1")

# Registers /api/v1/appointments/book, /list, and /complete/{id}
app.include_router(appointments.router, prefix="/api/v1")

# Registers /api/v1/prescriptions and /api/v1/prescriptions/create
app.include_router(prescriptions.router, prefix="/api/v1")

# Registers /api/v1/doctor/profile and /api/v1/doctor/patients
app.include_router(doctor.router, prefix="/api/v1")

# 🌟 FIX: Registers /api/v1/patient/profile — was missing entirely
app.include_router(patient.router, prefix="/api/v1")

# 🌟 FIX: Registers /api/v1/chat/ws/{room_id} and /api/v1/chat/history/{room_id}
#    (Use ai_chat.py, NOT chat.py — chat.py is a duplicate with no real JWT
#    signature verification. Delete app/api/endpoints/chat.py.)
app.include_router(ai_chat.router, prefix="/api/v1")

# 🌟 FIX: Registers /api/v1/visits/complete and /api/v1/visits/download-receipt/{id}
app.include_router(visits.router, prefix="/api/v1")


@app.get("/")
def read_root_status():
    return {
        "status": "online",
        "service": "MediAI Healthcare Core Node",
        "environment": "development"
    }
