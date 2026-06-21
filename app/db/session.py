from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base # 🔄 Added declarative_base
from app.core.config import settings

# 1. Create the async engine connected to your Neon database
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,   # Tests connections before running queries
    pool_recycle=300,     # Automatically drops and renews connections every 5 minutes
    pool_size=5,          # Keeps the connection footprint tiny for serverless limits
    max_overflow=10       # Allows temporary bursts under load
)

# 2. Create a session factory
# 🔄 Renamed to async_session_maker so our live chat persistence layer can call it!
async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# 🔑 NEW: Declare the missing Base class right here so all models can find it!
Base = declarative_base()

# 3. The dependency we inject into our FastAPI endpoints
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    # 🔄 Updated factory handle name inside the generator block
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()