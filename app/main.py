from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine, Base
# 🔄 The endpoints are imported cleanly here
from app.api.endpoints import auth, ai, appointments, ai_chat, doctor, prescriptions

# 🚨 ONLY ONE LIFESPAN BLOCK ALLOWED
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        print("⚠️ Initiating Complete Database Schema Nuke (CASCADE)...")
        
        # 1. Clear out the old schema layers completely
        #await conn.execute(text("DROP SCHEMA public CASCADE;"))
        #await conn.execute(text("CREATE SCHEMA public;"))
        
        # 🚀 FIX: Re-initialize the pgvector extension in your clean public schema frame!
        #await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        
        print("🌱 Rebuilding fresh, clean table structures starting at ID 1...")
        # Recreate empty tables fresh from your current SQLAlchemy models
        await conn.run_sync(Base.metadata.create_all)

        # Apply Your Custom Schema Alterations
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR DEFAULT 'Anonymous';"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR DEFAULT 'Patient';"))
        
        await conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS registration_number VARCHAR;"))
        await conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS password_hash VARCHAR;"))
        
    print("🚀 Neon Cloud Database hard reset complete! Everything is perfectly clean.")
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
# 📁 CONNECT ENDPOINT ROUTE TREES
# =========================================================
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(ai.router, prefix="/api/v1")
app.include_router(ai_chat.router, prefix="/api/v1") 
app.include_router(appointments.router, prefix="/api/v1")

# 🌟 FIX: Mounted the remaining routers to unlock profile, patient history, and prescription features!
app.include_router(doctor.router, prefix="/api/v1")
app.include_router(prescriptions.router, prefix="/api/v1")

@app.get("/")
def read_root():
    return {"status": "online", "engine": "MediAI Core Async Systems"}