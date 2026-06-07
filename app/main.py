from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.endpoints import ai,auth

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

# Register the AI routing module
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI & Voice Services"])

# Health Check Route
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
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(ai.router, prefix="/api/v1/ai", tags=["AI & Voice Services"])