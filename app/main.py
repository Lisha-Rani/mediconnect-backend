from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints import ai, auth, appointments, visits, chat
from sqlalchemy import text
# 🔄 DB Lifecycle Imports
from app.db.session import engine
from app.db.models import Base

# 🌐 THE STARTUP LIFESPAN MANAGER
# 🌐 THE STARTUP LIFESPAN MANAGER
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # 🛡️ SAFE ALTERATION: Injects the missing columns into the existing Neon table structure
        # If the columns already exist, PostgreSQL ignores this safely without throwing errors.
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"))
        
        # Verify and sync the remaining structural models 
        await conn.run_sync(Base.metadata.create_all)
        
    print("🚀 Neon Cloud Database Schema Sync Complete. All columns verified active!")
    yield
# Initialize the FastAPI app with the life-cycle manager attached
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="Backend API for MediAI Healthcare Management Platform",
    lifespan=lifespan 
)
# Initialize the FastAPI app with the life-cycle manager attached

# Configure Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🎛️ REGISTER APPLICATION ROUTERS (Preserving your exact prefix paths)
app.include_router(ai.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(appointments.router, prefix="/api/v1")
app.include_router(visits.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")

# --- SYSTEM UTILITY ROUTES ---

@app.get("/")
async def root():
    return {
        "status": "online",
        "project": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT
    }

@app.get("/health")
async def health_check():
    return {"message": "MediAI Systems fully operational"}