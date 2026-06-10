from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints import ai, auth,appointments,visits,chat

# Initialize the FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="Backend API for MediAI Healthcare Management Platform"
)

# Configure Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Restrict this to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Register AI Router 
# Changed prefix to "/api/v1" so it combines with "/ai" inside ai.py to make "/api/v1/ai/check"
# Removed tags override so it uses the clean tag defined inside ai.py
app.include_router(ai.router, prefix="/api/v1")

# 2. Register Authentication Router
app.include_router(auth.router, prefix="/api/v1/auth")
app.include_router(appointments.router, prefix="/api/v1")
app.include_router(visits.router, prefix="/api/v1")  # 👈 Mounts /api/v1/visits/complete and /download-receipt
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