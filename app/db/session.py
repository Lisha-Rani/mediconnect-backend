from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

# 1. Create the async engine connected to your Neon database
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True
)

# 2. Create a session factory
async_session = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

# 3. The dependency we inject into our FastAPI endpoints
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()