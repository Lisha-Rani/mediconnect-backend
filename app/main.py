from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.core.config import settings
from app.db.session import engine, Base
# 🔄 FIX: Import the chat router node explicitly
from app.api.endpoints import auth, ai, appointments, ai_chat 

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # 🛡️ Safe Schema Alterations
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR DEFAULT 'Anonymous';"))
        await conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR DEFAULT 'Patient';"))
        
        await conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS registration_number VARCHAR;"))
        await conn.execute(text("ALTER TABLE doctors ADD COLUMN IF NOT EXISTS password_hash VARCHAR;"))
        
        await conn.run_sync(Base.metadata.create_all)
        
    print("🚀 Neon Cloud Database Schema Sync Complete. Patient Names Activated!")
    yield
app = FastAPI(title="MediAI Backend Engine", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Connect Endpoint Route Trees
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(ai.router, prefix="/api/v1")
# 🔄 FIX: Mount the chat router structure into your API space
app.include_router(ai_chat.router, prefix="/api/v1") 

@app.get("/")
def read_root():
    return {"status": "online", "engine": "MediAI Core Async Systems"}