from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine, Base

# 📁 Direct Core Router Imports
from app.api.endpoints.auth import router as auth_router
from app.api.endpoints.ai import router as ai_router
from app.api.endpoints.appointments import router as appointments_router
from app.api.endpoints.ai_chat import router as ai_chat_router

# 🌟 CRITICAL CHANGE: Import directly without try/except protections. 
# If these files contain broken internal dependencies, your terminal will now show exactly what is broken!
from app.api.endpoints.doctor import router as doctors_router
from app.api.endpoints.prescriptions import router as prescriptions_router


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
# 📁 MOUNT ROUTER TREES TO LIFE (UNIFIED ROUTE MAPPING)
# =========================================================
app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(ai_router, prefix="/api/v1")
app.include_router(ai_chat_router, prefix="/api/v1") 
app.include_router(appointments_router, prefix="/api/v1")
app.include_router(doctors_router, prefix="/api/v1")
app.include_router(prescriptions_router, prefix="/api/v1")


@app.get("/")
def read_root():
    return {"status": "online", "engine": "MediAI Core Async Systems"}