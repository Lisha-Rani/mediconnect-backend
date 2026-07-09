from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine, Base

# =========================================================
# 🔄 FIX: DIRECT FILE PATH IMPORTS (Bypasses __init__.py bugs)
# =========================================================
from app.api.endpoints.auth import router as auth_router
from app.api.endpoints.ai import router as ai_router
from app.api.endpoints.appointments import router as appointments_router
from app.api.endpoints.ai_chat import router as ai_chat_router

# 🔎 Note: If your server flags either of these two lines below with a "ModuleNotFoundError",
# it means that specific .py file is either misspelled or missing from your folder!
try:
    from app.api.endpoints.doctors import router as doctors_router
except ModuleNotFoundError:
    try:
        from app.api.endpoints.doctor import router as doctors_router
    except ModuleNotFoundError:
        doctors_router = None

try:
    from app.api.endpoints.prescriptions import router as prescriptions_router
except ModuleNotFoundError:
    try:
        from app.api.endpoints.prescription import router as prescriptions_router
    except ModuleNotFoundError:
        prescriptions_router = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        print("🌱 Rebuilding clean table structures...")
        await conn.run_sync(Base.metadata.create_all)

        # Apply Your Custom Schema Alterations
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR DEFAULT 'Anonymous';"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR DEFAULT 'Patient';"))
        
        await conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS registration_number VARCHAR;"))
        await conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS password_hash VARCHAR;"))
        
    print("🚀 Neon Cloud Database Schema Sync Operational.")
    yield

app = FastAPI(title="MediAI Backend Engine", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================================================
# 📁 MOUNT EXPLICIT ROUTER TREES
# =========================================================
app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(ai_chat_router, prefix="/api/v1") 
app.include_router(appointments_router, prefix="/api/v1")

# Only mount these routers if the files were successfully located on your system
if doctors_router:
    app.include_router(doctors_router, prefix="/api/v1")
    print("➔ [MediAI Core] Successfully mounted Doctor Profile routes.")
else:
    print("⚠️ [MediAI Core] Warning: Doctor profile file not found. Skipping mount.")

if prescriptions_router:
    app.include_router(prescriptions_router, prefix="/api/v1")
    print("➔ [MediAI Core] Successfully mounted Prescription Archive routes.")
else:
    print("⚠️ [MediAI Core] Warning: Prescription file not found. Skipping mount.")


@app.get("/")
def read_root():
    return {"status": "online", "engine": "MediAI Core Async Systems"}