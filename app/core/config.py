from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "MediAI"
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    GOOGLE_API_KEY: str 
    HUGGINGFACE_API_KEY: str # Add this line
    # 1. Tell Pydantic to expect this variable
    ENVIRONMENT: str = "development"

    class Config:
        env_file = ".env"
        # 2. Tell Pydantic to ignore any other random variables in the .env file
        extra = "ignore" 

settings = Settings()