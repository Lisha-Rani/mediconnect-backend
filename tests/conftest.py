import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture(scope="session")
def anyio_backend():
    """
    Configures anyio to use the asyncio backend for async tests.
    """
    return "asyncio"

@pytest.fixture
async def async_client():
    """
    Provides an asynchronous HTTP client configured to communicate with the FastAPI app.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
#uvicorn app.main:app --reload --port 8001